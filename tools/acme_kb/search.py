"""Ranked search over memory/ and wiki/.

A record matches when every term occurs in it (case-insensitive substring). Those come first,
best first. Records that hold only some of the terms follow after a separator line, so one
unlucky word does not empty the result. The order is BM25 from an in-memory SQLite FTS5 table
built on each call: the repo is small, so there is no index file to go stale. The id, title,
summary, systems, tags and aliases weigh more than the body. Without FTS5 the same records
come back, ordered by how many terms they hold.
"""
import json
import re
import sqlite3
from contextlib import closing

from . import records

PARTIAL = "-- not every term matched --"
HEAD_WEIGHT = 5.0  # a term in the path or the head fields counts five times one in the body
HEAD_FIELDS = ("id", "title", "summary")
HEAD_LISTS = ("systems", "tags", "aliases")
TOKEN = re.compile(r"[^\W_]+")


def as_list(value):
    if not value:
        return []
    return [str(x) for x in value] if isinstance(value, list) else [str(value)]


def select(root, low, type=None, status=None, in_repo=None):
    """The records the filters pass, as dicts with the text search needs."""
    docs = []
    for rec in records.load(root):
        if type and rec.kind != type:
            continue
        # A wiki page names no repo and has no status. With terms, --in-repo and --status scope
        # the records that carry the field and keep the shared pages; without terms they list
        # the matching records only.
        shared = lambda field: bool(low) and field not in rec.meta
        if status and not shared("status") and rec.meta.get("status") != status:
            continue
        if in_repo and not shared("repos") and in_repo not in as_list(rec.meta.get("repos")):
            continue
        rel = rec.path.relative_to(root).as_posix()
        raw = rec.path.read_text()
        head = [rel] + [str(rec.meta.get(k, "")) for k in HEAD_FIELDS]
        head += [x for k in HEAD_LISTS for x in as_list(rec.meta.get(k))]
        docs.append({"rec": rec, "rel": rel, "raw": raw, "text": raw.lower(), "head": " ".join(head)})
    return docs


def fts_available():
    with closing(sqlite3.connect(":memory:")) as con:
        try:
            con.execute("create virtual table t using fts5(x)")
            return True
        except sqlite3.OperationalError:
            return False


def scores(docs, low):
    """BM25 per doc index for the docs that hold any term, lower is better; None without FTS5."""
    # `sym-links` becomes the phrase "sym links"; the trailing * also takes longer word forms
    phrases = [" ".join(TOKEN.findall(t)) for t in low]
    query = " OR ".join(f'"{ph}" *' for ph in phrases if ph)
    with closing(sqlite3.connect(":memory:")) as con:
        try:
            con.execute("create virtual table t using fts5(head, body, tokenize='porter unicode61')")
        except sqlite3.OperationalError:
            return None
        if not query:
            return {}
        con.executemany("insert into t(rowid, head, body) values (?, ?, ?)",
                        [(i, d["head"], d["raw"]) for i, d in enumerate(docs)])
        return dict(con.execute(f"select rowid, bm25(t, {HEAD_WEIGHT}, 1.0) from t where t match ?", (query,)))


def ranked(root, terms, type=None, status=None, in_repo=None):
    """(records holding every term, records holding some), each best first.
    Without terms: every record the filters pass, in path order, and no partial group."""
    low = [t.lower() for t in terms]
    docs = select(root, low, type=type, status=status, in_repo=in_repo)
    if not low:
        return docs, []
    bm25 = scores(docs, low)
    full, partial = [], []
    for i, d in enumerate(docs):
        held = sum(t in d["text"] for t in low)
        if not held and not (bm25 and i in bm25):
            continue
        key = (bm25.get(i, 0.0) if bm25 is not None else -held, d["rel"])
        (full if held == len(low) else partial).append((key, i))
    return [docs[i] for _, i in sorted(full)], [docs[i] for _, i in sorted(partial)]


def line(d):
    meta = d["rec"].meta
    return f"{d['rel']}  [{meta.get('status', d['rec'].kind)}]  {meta.get('summary', '')}"


def shown(full, partial, limit):
    """What fits in `limit` results (0: all): full matches first, partial ones fill the rest."""
    top = full[:limit] if limit else full
    if len(top) < len(full):
        return top, []
    return top, (partial[:limit - len(top)] if limit else partial)


def format_ranked(full, partial, limit=10):
    if not full and not partial:
        return "no records match; try a shorter or different word"
    top, rest = shown(full, partial, limit)
    lines = [line(d) for d in top]
    if len(top) < len(full):
        lines.append(f"({len(full) - len(top)} more with every term; --limit 0 shows all)")
    if rest:
        lines += [PARTIAL] + [line(d) for d in rest]
    return "\n".join(lines)


def record(d, match):
    meta = d["rec"].meta
    return {"path": d["rel"], "kind": d["rec"].kind, "match": match,
            "id": meta.get("id") or None, "status": meta.get("status") or None,
            "confidence": meta.get("confidence") or None, "summary": str(meta.get("summary", "")),
            "systems": as_list(meta.get("systems")), "repos": as_list(meta.get("repos")),
            "aliases": as_list(meta.get("aliases")),
            "updated": meta.get("updated") or None, "expires": meta.get("expires") or None}


def to_json(full, partial, limit, query):
    """The contract in search.schema.json; the limit works as in the text output."""
    top, rest = shown(full, partial, limit)
    return json.dumps({"schema_version": 1, "query": query,
                       "total": {"full": len(full), "partial": len(partial)},
                       "results": [record(d, "full") for d in top] + [record(d, "partial") for d in rest]},
                      ensure_ascii=False, indent=1)
