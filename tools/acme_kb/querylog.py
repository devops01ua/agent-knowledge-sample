"""A local log of searches, to see how often search misses.

Every `acme-kb search` with terms appends one JSON line to `.queries/YYYY-MM.jsonl` in the
checkout: the terms, the filters, how many records held every term and how many only some,
the first paths and the repository the search was run from. The directory is ignored by git,
so the log stays on the laptop that made it. `acme-kb queries` reports from it.
`ACME_KB_NO_QUERY_LOG=1` switches it off. A failure to write never fails the search.
"""
import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

DIR = ".queries"
WINDOW = timedelta(minutes=5)  # another search from the same repo within this rephrases the last one


def path(root, now=None):
    now = now or datetime.now(timezone.utc)
    return Path(root) / DIR / f"{now:%Y-%m}.jsonl"


def repo_of(cwd):
    for candidate in (cwd, *cwd.parents):
        if (candidate / ".git").exists():
            return candidate.name
    return ""


def record(root, terms, flags, full, partial, top, now=None, repo=None):
    if os.environ.get("ACME_KB_NO_QUERY_LOG") or not terms:
        return None
    now = now or datetime.now(timezone.utc)
    row = {"ts": now.isoformat(timespec="seconds"), "terms": list(terms),
           "flags": {k: v for k, v in flags.items() if v}, "full": full, "partial": partial,
           "top": list(top[:3]), "repo": repo_of(Path.cwd()) if repo is None else repo}
    target = path(root, now)
    try:
        target.parent.mkdir(exist_ok=True)
        with target.open("a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        return None
    return target


def read(root, days=30, now=None):
    """Rows of the last `days` days, oldest first; 0 means all."""
    since = (now or datetime.now(timezone.utc)) - timedelta(days=days) if days else None
    folder = Path(root) / DIR
    rows = []
    for f in sorted(folder.glob("*.jsonl")) if folder.is_dir() else []:
        for raw in f.read_text().splitlines():
            try:
                row = json.loads(raw)
                row["_ts"] = datetime.fromisoformat(row["ts"])
            except (ValueError, KeyError, TypeError):
                continue
            if since is None or row["_ts"] >= since:
                rows.append(row)
    return sorted(rows, key=lambda r: r["_ts"])


def label(row):
    flags = sorted(row.get("flags", {}).items())
    return " ".join(row["terms"] + [f"--{k.replace('_', '-')} {v}" for k, v in flags])


def report(rows):
    rephrased = sum(1 for i, r in enumerate(rows)
                    if any(n.get("repo") == r.get("repo") and n["terms"] != r["terms"]
                           and n["_ts"] - r["_ts"] <= WINDOW for n in rows[i + 1:i + 20]))
    missed = [r for r in rows if not r.get("full")]
    return {"searches": len(rows), "no_full": len(missed), "rephrased": rephrased,
            "misses": Counter(label(r) for r in missed)}


def format_report(rep):
    n = rep["searches"]
    if not n:
        return "no searches logged"
    share = lambda k: f"{rep[k]} ({rep[k] / n:.0%})"
    lines = [f"searches: {n}", f"without a full match: {share('no_full')}",
             f"rephrased within {int(WINDOW.total_seconds() // 60)} minutes: {share('rephrased')}"]
    if rep["misses"]:
        lines.append("top misses, candidates for an alias or a page:")
        lines += [f"  {count} x {query}" for query, count in rep["misses"].most_common(10)]
    return "\n".join(lines)
