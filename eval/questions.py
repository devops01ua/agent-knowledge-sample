"""Relation questions with ground truth computed from the repo itself, not from the tool under test.

    PYTHONPATH=tools python3 eval/questions.py > eval/questions.json

Three kinds: is this record still current (supersede chain), who cites this record or page
(backlinks), and what else is open on the same system (neighbours). The answer is a set of ids
and paths read straight from the files: frontmatter and [[links]] / ids in the text.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from acme_kb import records  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
IDS = re.compile(r"\b[FDI]-\d{4}-\d{2}-\d{2}-\d{3}\b")

recs = records.load(ROOT)
pathkey = lambda r: r.path.relative_to(ROOT).with_suffix("").as_posix()
key_of = {pathkey(r): (r.meta.get("id") or pathkey(r)) for r in recs}  # a record is named by its id, a page by its path
cites = defaultdict(set)
for r in recs:
    me = key_of[pathkey(r)]
    for target in records.LINK.findall(r.body):
        cites[key_of.get(target.strip(), target.strip())].add(me)
    for i in IDS.findall(r.body):
        if i != r.meta.get("id"):
            cites[i].add(me)

out = []
for r in recs:
    rid = r.meta.get("id")
    if r.meta.get("superseded_by"):
        chain, cur = [], r
        while cur.meta.get("superseded_by"):
            chain.append(cur.meta["superseded_by"])
            cur = next(x for x in recs if x.meta.get("id") == cur.meta["superseded_by"])
        out.append({"id": f"S-{rid}", "kind": "supersede", "expected": [chain[-1]],
                    "q": f"Is {r.kind} {rid} still current? If it was replaced, give the id that replaced it."})
    k = key_of[pathkey(r)]
    if len(cites.get(k, ())) >= 2:
        out.append({"id": "B-" + k.replace("/", "_"), "kind": "backlinks", "expected": sorted(cites[k]),
                    "q": f"Which records and pages cite {k}? List every id or path."})
for system in sorted({s for r in recs for s in (r.meta.get("systems") or [])}):
    open_ = sorted(r.meta["id"] for r in recs if system in (r.meta.get("systems") or []) and r.meta.get("status") == "open")
    if len(open_) >= 2:
        out.append({"id": f"N-{system}", "kind": "neighbours", "expected": open_,
                    "q": f"Which open records exist for the system {system}? List their ids."})
print(json.dumps(out, indent=1))
