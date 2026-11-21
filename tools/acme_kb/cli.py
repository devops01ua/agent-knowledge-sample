import argparse
import datetime as dt
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

from . import kb, querylog, read, records, related, search

DEFAULT_URL = "https://github.com/devops01ua/agent-knowledge-sample.git"


def home():
    return Path(os.environ.get("ACME_HOME") or Path.home())


def checkout_dir():
    return Path(os.environ.get("ACME_KNOWLEDGE_HOME") or home() / ".acme-knowledge")


def is_repo(path):
    path = Path(path)
    return (path / "AGENTS.md").is_file() and (path / "memory").is_dir()


def find_root(arg):
    for candidate in (arg, os.environ.get("ACME_KNOWLEDGE_HOME"), Path.cwd(), checkout_dir()):
        if candidate and is_repo(candidate):
            return Path(candidate).resolve()
    sys.exit("not inside a knowledge repo: run `acme-kb setup` first, or pass --repo PATH")


def git(root, *args, check=True):
    return subprocess.run(["git", "-C", str(root), *args], check=check, capture_output=True, text=True)


def cmd_setup(args):
    dest = checkout_dir()
    if (dest / ".git").is_dir():
        subprocess.run(["git", "-C", str(dest), "pull", "--ff-only"], check=True)
    else:
        subprocess.run(["git", "clone", args.url, str(dest)], check=True)
    print(f"knowledge checkout: {dest}")
    link_skills(dest, args.link_skills or [home() / ".claude" / "skills", home() / ".agents" / "skills"])


def link_skills(dest, targets):
    for target in targets:
        target = Path(target)
        target.mkdir(parents=True, exist_ok=True)
        for skill in sorted((dest / ".agents" / "skills").iterdir()):
            link = target / skill.name
            if link.is_symlink():
                link.unlink()
            elif link.exists():
                print(f"  kept existing {link}")
                continue
            link.symlink_to(skill, target_is_directory=True)
            print(f"  skill {link}")


def cmd_sync(args):
    root = find_root(args.repo)
    out = git(root, "pull", "--ff-only", check=False)
    print((out.stdout or out.stderr).strip() or "up to date")
    return out.returncode


def cmd_search(args):
    root = find_root(args.repo)
    filters = {"type": args.type, "status": args.status, "in_repo": args.in_repo}
    meaning = None
    if args.kb and args.words:
        def meaning(text):
            try:
                return kb.retrieve(text)
            except kb.Unavailable as e:
                print(f"(keywords only: {e})", file=sys.stderr)
                return []
    full, partial = search.ranked(root, args.words, meaning=meaning, **filters)
    querylog.record(root, args.words, filters, len(full), len(partial), [d["rel"] for d in full + partial])
    limit = args.limit if args.words else 0
    if args.json:
        print(search.to_json(full, partial, limit, {"terms": args.words, **filters, "limit": limit}))
    else:
        print(search.format_ranked(full, partial, limit))
    return 0


def cmd_get(args):
    root = find_root(args.repo)
    try:
        d = read.get(root, args.ref, fields=args.fields.split(",") if args.fields else None, sections=args.section)
    except read.NotFound as e:
        print(f"acme-kb get: {e}", file=sys.stderr)
        return 1
    print(read.format(d))
    return 0


def cmd_list(args):
    root = find_root(args.repo)
    docs, _ = search.ranked(root, [], type=args.type, status=args.status, in_repo=args.in_repo)
    if args.system:
        docs = [d for d in docs if args.system in search.as_list(d["rec"].meta.get("systems"))
                or d["rel"] == f"wiki/systems/{args.system}.md"]
    print("\n".join(search.line(d) for d in docs) or "nothing matches these filters")
    return 0


def cmd_related(args):
    root = find_root(args.repo)
    try:
        d = related.related(root, args.ref, limit=max(1, args.limit))
    except read.NotFound as e:
        print(f"acme-kb related: {e}", file=sys.stderr)
        return 1
    print(related.format(d))
    return 0


def cmd_kb_export(args):
    root = find_root(args.repo)
    print(f"{kb.export(root, Path(args.out))} documents in {args.out}")
    return 0


MCP_SNIPPET = """{
  "mcpServers": {
    "acme-kb": {
      "type": "http",
      "url": "${ACME_KB_MCP_URL}",
      "headers": {"Authorization": "Bearer ${ACME_KB_MCP_TOKEN}", "X-Acme-KB-Client": "claude-code/<you>"}
    }
  }
}"""


def cmd_mcp(args):
    print("The server in mcp/ serves kb_search, kb_get, kb_list and kb_related over the same functions.")
    print("Local, no server: python mcp/server.py --stdio. Remote: put this in .mcp.json (Claude Code):\n")
    print(MCP_SNIPPET)
    return 0


def cmd_queries(args):
    root = find_root(args.repo)
    print(querylog.format_report(querylog.report(querylog.read(root, days=args.days))))
    return 0


def next_id(root, kind, today):
    spec = records.KINDS[kind]
    stem = f"{spec['prefix']}-{today.isoformat()}-"
    used = [int(p.stem[-3:]) for p in (root / spec["dir"]).glob(stem + "*.md")]
    return f"{stem}{max(used, default=0) + 1:03d}"


def cmd_new(args):
    root = find_root(args.repo)
    today = dt.date.today()
    rid = next_id(root, args.kind, today)
    text = (root / "templates" / f"{args.kind}.md").read_text()
    text = (text.replace("{{id}}", rid).replace("{{summary}}", args.summary.replace('"', "'"))
            .replace("{{today}}", today.isoformat())
            .replace("{{expires}}", (today + dt.timedelta(days=180)).isoformat())
            .replace("{{author}}", os.environ.get("USER", "unknown")))
    path = root / records.KINDS[args.kind]["dir"] / f"{rid}.md"
    path.write_text(text)
    print(path.relative_to(root))


def cmd_validate(args):
    root = find_root(args.repo)
    errors, warnings = records.check(root)
    for line in warnings:
        print("warning:", line)
    for line in errors:
        print("error:", line)
    print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


def cmd_capture(args):
    root = find_root(args.repo)
    matches = [r for r in records.load(root) if r.meta.get("id") == args.id]
    if not matches:
        sys.exit(f"no record with id {args.id}")
    errors, _ = records.check(root)
    rel = str(matches[0].path.relative_to(root))
    mine = [e for e in errors if e.startswith(rel + ":")]
    if mine:
        print("\n".join(mine))
        sys.exit("fix the record first")
    branch = f"capture/{args.id}"
    git(root, "switch", "-c", branch)
    git(root, "add", rel)
    git(root, "commit", "-m", f"capture {args.id}: {matches[0].meta.get('summary', '')[:60]}")
    print(f"committed on {branch}")
    print(f"next: git -C {root} push -u origin {branch}   and open a pull request")


INDEX_NOTE = "Generated by `acme-kb gen-index`. Not tracked in git."


def build_index_full(root):
    """index-full.md: one line per record."""
    lines = ["# Index: every record", "", INDEX_NOTE, ""]
    for rec in records.load(root):
        rel = rec.path.relative_to(root)
        label = rec.meta.get("id") or rel.stem
        lines.append(f"- [{label}]({rel}) [{rec.meta.get('status', rec.kind)}] {rec.meta.get('summary', '')}")
    return "\n".join(lines) + "\n"


def build_index_map(root):
    """index.md: one line per system with its page and how many records name it, open ones counted."""
    pages, others, named, open_ = {}, [], Counter(), Counter()
    for rec in records.load(root):
        rel = rec.path.relative_to(root)
        if rec.kind == "wiki" and rel.parent.as_posix() == "wiki/systems":
            pages[rel.stem] = (rel, rec.meta.get("summary", ""))
        elif rec.kind == "wiki":
            others.append(f"- [{rel.stem}]({rel}) {rec.meta.get('summary', '')}")
        else:
            for system in set(search.as_list(rec.meta.get("systems"))):
                named[system] += 1
                open_[system] += rec.meta.get("status") == "open"
    lines = ["# Index: systems", "", INDEX_NOTE, "",
             "One line per system: its page, then how many records name it and how many of those are open.",
             "Records of a system: `acme-kb search <system>`. Every record with its summary: `index-full.md`.",
             "", "## Systems", ""]
    for system in sorted(set(pages) | set(named), key=str.lower):
        rel, summary = pages.get(system, (None, ""))
        page = f"[page]({rel})" if rel else "no page"
        lines.append(f"- {system} · {page} · open {open_[system]} of {named[system]}" + (f" · {summary}" if summary else ""))
    if others:
        lines += ["", "## Other pages", ""] + others
    return "\n".join(lines) + "\n"


def cmd_gen_index(args):
    root = find_root(args.repo)
    (root / "index.md").write_text(build_index_map(root))
    (root / "index-full.md").write_text(build_index_full(root))
    print(f"index.md: a map of the systems; index-full.md: {len(records.load(root))} records")


def cmd_init_repo(args):
    target = Path(args.path).resolve() / "AGENTS.md"
    if target.exists():
        print(f"{target} already exists, left as is")
        return 0
    template = find_root(args.repo) / "templates" / "compass.md"
    shutil.copy(template, target)
    print(f"wrote {target}: fill in what the repo is for, its commands, traps and dependencies")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="acme-kb", description=__doc__)
    parser.add_argument("--repo", help="path to a knowledge repo")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("setup", help="clone the knowledge repo and link its skills")
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument("--link-skills", action="append", help="skills directory to link into (repeatable)")
    p.set_defaults(func=cmd_setup)

    sub.add_parser("sync", help="pull the fresh knowledge").set_defaults(func=cmd_sync)

    p = sub.add_parser("search", help="ranked search over every record")
    p.add_argument("words", nargs="*", help="without words: list every record the filters pass")
    p.add_argument("--type", choices=sorted(records.KINDS))
    p.add_argument("--status")
    p.add_argument("--in-repo", help="only records about this repository; with words, wiki pages stay")
    p.add_argument("--limit", type=int, default=10, help="results to print for a search with words; 0 for all")
    p.add_argument("--json", action="store_true", help="print the results as tools/acme_kb/search.schema.json describes")
    p.add_argument("--kb", action="store_true", help="also rank by meaning with the knowledge base in ACME_KB_ID")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("get", help="one record's fields or one page's sections, not the whole file")
    p.add_argument("ref", help="an id, a repo path or a system name")
    p.add_argument("--fields", help="comma-separated fields; the working ones by default; `body` for the text")
    p.add_argument("--section", action="append", help="a page section by heading; repeatable; without it a page gives its outline")
    p.set_defaults(func=cmd_get)

    p = sub.add_parser("list", help="records by type, status, repo or system, one line each")
    p.add_argument("--type", choices=sorted(records.KINDS))
    p.add_argument("--status")
    p.add_argument("--in-repo")
    p.add_argument("--system")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("related", help="what a record connects to: supersede chain, links, cited by, same systems")
    p.add_argument("ref")
    p.add_argument("--limit", type=int, default=5, help="lines per group")
    p.set_defaults(func=cmd_related)

    p = sub.add_parser("kb-export", help="write every record as knowledge-base documents with metadata")
    p.add_argument("out")
    p.set_defaults(func=cmd_kb_export)

    sub.add_parser("mcp", help="how to reach the same tools over MCP").set_defaults(func=cmd_mcp)

    p = sub.add_parser("queries", help="report from the local search log (.queries/, not tracked)")
    p.add_argument("--days", type=int, default=30, help="look back this many days; 0 for all")
    p.set_defaults(func=cmd_queries)

    p = sub.add_parser("new", help="create a record from its template")
    p.add_argument("kind", choices=["finding", "decision", "incident"])
    p.add_argument("summary")
    p.set_defaults(func=cmd_new)

    sub.add_parser("validate", help="check every record against the schema").set_defaults(func=cmd_validate)

    p = sub.add_parser("capture", help="validate one record and commit it on its own branch")
    p.add_argument("id")
    p.set_defaults(func=cmd_capture)

    sub.add_parser("gen-index", help="write the local index.md (system map) and index-full.md").set_defaults(func=cmd_gen_index)

    p = sub.add_parser("init-repo", help="add an AGENTS.md compass to a code repository")
    p.add_argument("path")
    p.set_defaults(func=cmd_init_repo)

    args = parser.parse_args(argv)
    return args.func(args) or 0
