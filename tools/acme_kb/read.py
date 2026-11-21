"""Read one record in part, so an agent does not pull a whole file into its context.

A record keeps its content in frontmatter fields, so the caller names the fields it needs and
gets the working ones by default. A wiki page keeps it under headings: without `sections` the
answer is the page's outline, and the caller asks for the sections it wants.
"""
import re
from pathlib import Path

from . import records

DEFAULT_FIELDS = {
    "finding": ["id", "status", "confidence", "summary", "symptom", "root_cause", "fix"],
    "decision": ["id", "status", "summary", "decision", "rejected", "superseded_by"],
    "incident": ["id", "status", "summary", "impact", "root_cause", "fix"],
    "wiki": ["summary", "owner", "updated"],
}
HEADING = re.compile(r"^(#{2,3})\s+(.*?)\s*$", re.M)


class NotFound(LookupError):
    pass


def resolve(root, ref):
    """An id (F-2026-09-20-001), a repo path (with or without .md) or a system name. Paths
    outside the repo and symlinks are refused."""
    root = Path(root).resolve()
    ref = ref.strip()
    if records.ID.match(ref):
        for rec in records.load(root):
            if rec.meta.get("id") == ref:
                return rec
        raise NotFound(f"no record with id {ref}")
    for cand in (ref, f"{ref}.md", f"wiki/systems/{ref}.md"):
        p = root / cand
        if p.suffix == ".md" and p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(root):
            return records.parse(p)
    raise NotFound(f"no page {ref}: give an id, a repo path or a system name")


def sections_of(body):
    """[(heading, text)] for the ## and ### headings of a page body."""
    marks = list(HEADING.finditer(body))
    return [(m.group(2), body[m.end():marks[i + 1].start() if i + 1 < len(marks) else len(body)].strip())
            for i, m in enumerate(marks)]


def get(root, ref, fields=None, sections=None):
    rec = resolve(root, ref)
    kind = rec.kind or "wiki"
    out = {"path": rec.path.relative_to(Path(root).resolve()).as_posix(), "kind": kind,
           "fields": {}, "sections": [], "outline": [], "missing": []}
    for f in fields or DEFAULT_FIELDS.get(kind, list(rec.meta)):
        if f == "body":
            out["fields"]["body"] = rec.body.strip()
        elif f in rec.meta:
            out["fields"][f] = rec.meta[f]
        elif fields:
            out["missing"].append(f)
    secs = sections_of(rec.body)
    if sections:
        for name in sections:
            low = name.lower()
            hit = next((s for s in secs if s[0].lower() == low), None) or next((s for s in secs if low in s[0].lower()), None)
            out["sections"].append(hit) if hit else out["missing"].append(f"section: {name}")
    elif kind == "wiki":
        out["outline"] = [h for h, _ in secs]
    return out


def format(d):
    """Plain `key: value` lines: as readable for a model as JSON, and fewer tokens."""
    lines = [d["path"]]
    for k, v in d["fields"].items():
        if k != "body":
            lines.append(f"{k}: {', '.join(map(str, v)) if isinstance(v, list) else v}")
    if d["fields"].get("body"):
        lines += ["", d["fields"]["body"]]
    for heading, text in d["sections"]:
        lines += ["", f"## {heading}", text]
    if d["outline"]:
        lines += ["", "sections: " + " · ".join(d["outline"])]
    if d["missing"]:
        lines += ["", "not on this page: " + ", ".join(d["missing"])]
    return "\n".join(lines)
