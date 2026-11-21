"""acme-kb over MCP: the same functions as the CLI, as four read-only tools.

    kb_search   ranked search, typed terms and filters, optional ranking by meaning
    kb_get      one record's working fields or one page's sections
    kb_list     records by type, status, repo or system
    kb_related  supersede chain, links, cited by, other open records on the same systems

Answers are plain `key: value` lines in the CLI format, not JSON: in our measurements indented
JSON cost a third more tool output for the same answers.

Every call writes one JSON line to stderr (stdout carries the protocol in --stdio mode) (tool, caller, parameters, paths returned, bytes,
latency), never page text. Ship it to your log store; a metric and a trace per call are a few
lines more with prometheus_client and OpenTelemetry.

Run:
    python mcp/server.py --stdio                        # one agent on this laptop
    ACME_KB_MCP_TOKEN=... python mcp/server.py --http   # a shared server, bearer token, port 8080
The repo is the current directory or ACME_KNOWLEDGE_HOME; keep it fresh with a `git pull` loop.
"""
import argparse
import hmac
import json
import os
import sys
import time
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from acme_kb import kb, read, related, search  # noqa: E402
from mcp.server.fastmcp import Context, FastMCP  # noqa: E402

ROOT = Path(os.environ.get("ACME_KNOWLEDGE_HOME") or Path.cwd()).resolve()
Kind = Literal["finding", "decision", "incident", "wiki"]
Status = Literal["open", "fixed", "accepted", "accepted-risk", "superseded", "closed"]
mcp = FastMCP("acme-kb", stateless_http=True, json_response=True)


def caller(ctx):
    try:
        return ctx.request_context.request.headers.get("x-acme-kb-client", "unknown")
    except Exception:
        return "stdio"


def observed(tool, params, ctx, fn):
    t = time.monotonic()
    try:
        text, paths = fn()
        out = {"tool": tool, "caller": caller(ctx), **{k: v for k, v in params.items() if v not in (None, [], "")},
               "paths": paths[:5], "bytes": len(text.encode()), "ms": round((time.monotonic() - t) * 1000)}
        print(json.dumps(out, ensure_ascii=False), file=sys.stderr, flush=True)
        return text
    except Exception as e:
        print(json.dumps({"tool": tool, "error": f"{type(e).__name__}: {e}"[:200]}), file=sys.stderr, flush=True)
        raise


@mcp.tool()
def kb_search(terms: list[str], kind: Kind | None = None,
              status: Status | None = None, repo: str | None = None, meaning: bool = True,
              limit: int = 5, ctx: Context | None = None) -> str:
    """Search the team's knowledge repo: findings, decisions, incidents and system pages.

    terms: the words, one per item, e.g. ["gitops", "token"].
    kind / status / repo: filters. limit: 1-20 results (default 5).
    Lines after "-- not every term matched --" hold only some words. Read a result with kb_get."""
    words = [w for t in terms for w in str(t).split()]

    def run():
        note = []

        def by_meaning(text):
            try:
                return kb.retrieve(text)
            except kb.Unavailable as e:
                note.append(f"(keywords only: {e})")
                return []
        full, partial = search.ranked(ROOT, words, type=kind, status=status, in_repo=repo,
                                      meaning=by_meaning if meaning else None)
        text = search.format_ranked(full, partial, max(1, min(limit, 20)))
        return "\n".join(note + [text]), [d["rel"] for d in full + partial]
    return observed("kb_search", {"terms": words, "kind": kind, "status": status, "repo": repo}, ctx, run)


@mcp.tool()
def kb_get(ref: str, fields: list[str] | None = None, sections: list[str] | None = None,
           ctx: Context | None = None) -> str:
    """Read one record or page in part. ref: an id (F-2026-09-20-001), a path or a system name.
    fields: for a record, the fields to return (working ones by default; `body` for the text).
    sections: for a page, the headings to return; without them a page answers with its outline."""
    def run():
        try:
            d = read.get(ROOT, ref, fields=fields, sections=sections)
        except read.NotFound as e:
            return f"not found: {e}", []
        return read.format(d), [d["path"]]
    return observed("kb_get", {"ref": ref, "fields": fields, "sections": sections}, ctx, run)


@mcp.tool()
def kb_list(kind: Kind | None = None, status: Status | None = None, repo: str | None = None,
            system: str | None = None, ctx: Context | None = None) -> str:
    """List records with their summaries, e.g. every open finding about a system. Use it when a
    search finds nothing and you know the system, instead of reading an index file."""
    def run():
        docs, _ = search.ranked(ROOT, [], type=kind, status=status, in_repo=repo)
        if system:
            docs = [d for d in docs if system in search.as_list(d["rec"].meta.get("systems"))]
        return "\n".join(search.line(d) for d in docs) or "nothing matches", [d["rel"] for d in docs]
    return observed("kb_list", {"kind": kind, "status": status, "repo": repo, "system": system}, ctx, run)


@mcp.tool()
def kb_related(ref: str, limit: int = 5, ctx: Context | None = None) -> str:
    """What one record or page connects to, in one call: whether it was superseded and by what,
    what it links to, which records and pages cite it, and the other open records on the same
    systems. Use it for "is this still current", "who refers to this", "what else do we know"."""
    def run():
        try:
            d = related.related(ROOT, ref, limit=max(1, min(limit, 20)))
        except read.NotFound as e:
            return f"not found: {e}", []
        return related.format(d, get_hint='kb_get ref="ID or path"'), [d["page"]["path"]]
    return observed("kb_related", {"ref": ref, "limit": limit}, ctx, run)


class BearerAuth:
    def __init__(self, app, token):
        self.app, self.token = app, token.encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            got = dict(scope.get("headers") or []).get(b"authorization", b"")
            if not hmac.compare_digest(got, b"Bearer " + self.token):
                await send({"type": "http.response.start", "status": 401, "headers": [(b"content-type", b"text/plain")]})
                await send({"type": "http.response.body", "body": b"unauthorized"})
                return
        await self.app(scope, receive, send)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stdio", action="store_true")
    ap.add_argument("--http", action="store_true")
    ap.add_argument("--port", type=int, default=8080)
    a = ap.parse_args()
    if a.http:
        import uvicorn
        token = os.environ.get("ACME_KB_MCP_TOKEN") or sys.exit("set ACME_KB_MCP_TOKEN")
        uvicorn.run(BearerAuth(mcp.streamable_http_app(), token), host="0.0.0.0", port=a.port)
    else:
        mcp.run()
