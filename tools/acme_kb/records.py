"""Read records (markdown with a small frontmatter) and check them against the schema."""
import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path

KINDS = {
    "finding": {
        "dir": "memory/findings", "prefix": "F",
        "required": ["id", "type", "status", "severity", "repos", "systems", "summary",
                     "symptom", "root_cause", "fix", "evidence", "author", "confidence",
                     "updated", "expires"],
        "status": ["open", "fixed", "accepted-risk", "superseded"],
    },
    "decision": {
        "dir": "memory/decisions", "prefix": "D",
        "required": ["id", "type", "status", "repos", "summary", "context", "decision",
                     "rejected", "author", "updated"],
        "status": ["accepted", "superseded"],
    },
    "incident": {
        "dir": "memory/incidents", "prefix": "I",
        "required": ["id", "type", "status", "severity", "systems", "summary", "impact",
                     "root_cause", "fix", "author", "updated"],
        "status": ["open", "closed"],
    },
    "wiki": {
        "dir": "wiki", "prefix": None,
        "required": ["type", "summary", "owner", "updated"],
        "status": [],
    },
}
ENUMS = {
    "severity": ["low", "medium", "high"],
    "confidence": ["verified", "assumed"],
}
LIST_FIELDS = {"repos", "systems", "evidence", "rejected", "sources"}
# Optional on every record and page: the other names people search by. Written as [a, b] or
# not at all; a bare value is an error, not a list of one.
STRICT_LISTS = {"aliases"}
DATE_FIELDS = {"updated", "expires"}
SYSTEM_SECTIONS = ["## What it is", "## How we run it", "## Traps"]
LINK = re.compile(r"\[\[([^\]|#]+)")
ID = re.compile(r"^[FDI]-\d{4}-\d{2}-\d{2}-\d{3}$")


@dataclass
class Record:
    path: Path
    meta: dict
    body: str

    @property
    def kind(self):
        return self.meta.get("type", "")

    @property
    def text(self):
        return self.path.read_text()


def parse_value(key, raw):
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        return [item.strip().strip("\"'") for item in raw[1:-1].split(",") if item.strip()]
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        raw = raw[1:-1]
    return [raw] if key in LIST_FIELDS and raw else raw


def parse(path):
    """Frontmatter is flat `key: value` lines between two `---` lines."""
    text = Path(path).read_text()
    if not text.startswith("---\n"):
        return Record(Path(path), {}, text)
    head, _, body = text[4:].partition("\n---\n")
    meta = {}
    for line in head.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = parse_value(key.strip(), value)
    return Record(Path(path), meta, body)


def load(root):
    root = Path(root)
    records = []
    for folder in ("memory", "wiki"):
        for path in sorted((root / folder).rglob("*.md")):
            records.append(parse(path))
    return records


def link_targets(root):
    root = Path(root)
    return {str(p.relative_to(root).with_suffix("")) for folder in ("memory", "wiki", "raw")
            for p in (root / folder).rglob("*.md")}


def check(root, today=None):
    """Return (errors, warnings) as lists of 'path: message'."""
    root = Path(root)
    today = today or dt.date.today()
    errors, warnings = [], []
    targets = link_targets(root)
    seen_ids = {}
    for rec in load(root):
        rel = rec.path.relative_to(root)
        err = lambda msg: errors.append(f"{rel}: {msg}")
        spec = KINDS.get(rec.kind)
        if not rec.meta:
            err("no frontmatter"); continue
        if not spec:
            err(f"unknown type {rec.kind!r}"); continue
        if not str(rel).startswith(spec["dir"] + "/"):
            err(f"a {rec.kind} belongs under {spec['dir']}/")
        for key in spec["required"]:
            if key not in rec.meta or rec.meta[key] in ("", []):
                err(f"missing field {key}")
        if spec["status"] and rec.meta.get("status") not in spec["status"]:
            err(f"status must be one of {', '.join(spec['status'])}")
        for key, allowed in ENUMS.items():
            if key in rec.meta and rec.meta[key] not in allowed:
                err(f"{key} must be one of {', '.join(allowed)}")
        for key in STRICT_LISTS & rec.meta.keys():
            if not isinstance(rec.meta[key], list):
                err(f"{key} must be a list like [a, b]")
        dates = {}
        for key in DATE_FIELDS & rec.meta.keys():
            try:
                dates[key] = dt.date.fromisoformat(rec.meta[key])
            except ValueError:
                err(f"{key} is not a date (YYYY-MM-DD)")
        if spec["prefix"]:
            rid = rec.meta.get("id", "")
            if not ID.match(rid) or rid[0] != spec["prefix"]:
                err(f"id must look like {spec['prefix']}-YYYY-MM-DD-NNN")
            if rid != rec.path.stem:
                err("id and file name differ")
            if rid in seen_ids:
                err(f"id already used by {seen_ids[rid]}")
            seen_ids[rid] = rel
        summary = rec.meta.get("summary", "")
        if isinstance(summary, str) and len(summary) > 240:
            err("summary is longer than 240 characters; one sentence you can act on")
        if rec.kind == "finding" and rec.meta.get("confidence") == "verified" and not rec.meta.get("evidence"):
            err("confidence: verified needs evidence")
        if str(rel).startswith("wiki/systems/"):
            for section in SYSTEM_SECTIONS:
                if section not in rec.body:
                    err(f"system page lacks the section '{section}'")
        for target in LINK.findall(rec.body):
            if target.strip() not in targets:
                err(f"dead link [[{target.strip()}]]")
        if rec.meta.get("status") == "open" and "expires" in dates and dates["expires"] < today:
            warnings.append(f"{rel}: open and expired on {dates['expires']}; fix it, renew it or close it")
    return errors, warnings
