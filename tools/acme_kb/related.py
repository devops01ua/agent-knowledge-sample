"""What one record or page connects to, in one answer.

The relations are already in the files; without this an agent follows them one `get` at a time,
and "who cites this page" cannot be seen without reading every file.

- links: [[...]] links and record ids written in the text (a link and an id to the same record count once);
- cited by: records and pages whose text links here or names this id;
- chain: `superseded_by` followed to the current record, and the records this one replaced;
- systems: the other records about the same systems, open ones listed, the rest counted.
"""
import re
from pathlib import Path

from . import read, records

ID_IN_TEXT = re.compile(r"\b[FDI]-\d{4}-\d{2}-\d{2}-\d{3}\b")
SUMMARY_CHARS = 120


def corpus(root):
    root = Path(root).resolve()
    out = {}
    for rec in records.load(root):
        rel = rec.path.relative_to(root).as_posix()
        out[rel] = {"rel": rel, "meta": rec.meta,
                    "links": sorted({l.strip() + ".md" for l in records.LINK.findall(rec.body)}),
                    "ids": sorted(set(ID_IN_TEXT.findall(rec.body)) - {rec.meta.get("id")})}
    return out


def _line(d):
    m = d["meta"]
    return {"path": d["rel"], "id": m.get("id"), "status": m.get("status"), "summary": str(m.get("summary", ""))}


def related(root, ref, limit=5):
    root = Path(root).resolve()
    me_path = read.resolve(root, ref).path.relative_to(root).as_posix()
    docs = corpus(root)
    by_id = {d["meta"]["id"]: d for d in docs.values() if d["meta"].get("id")}
    me = docs[me_path]
    my_id = me["meta"].get("id")

    chain, cur, seen = [], me, {my_id}
    while cur["meta"].get("superseded_by") and cur["meta"]["superseded_by"] not in seen:
        nxt = by_id.get(cur["meta"]["superseded_by"])
        if not nxt:
            break
        seen.add(nxt["meta"]["id"])
        chain.append(_line(nxt))
        cur = nxt
    replaces = [_line(d) for d in docs.values() if my_id and d["meta"].get("superseded_by") == my_id]

    links = [_line(docs[t]) for t in me["links"] if t in docs]
    linked = set(me["links"])
    links += [_line(by_id[i]) for i in me["ids"] if i in by_id and by_id[i]["rel"] not in linked]
    cited = [_line(d) for d in docs.values()
             if d["rel"] != me_path and (me_path in d["links"] or (my_id and my_id in d["ids"]))]

    names = records_systems(me) or ([Path(me_path).stem] if me_path.startswith("wiki/systems/") else [])
    systems = {}
    for s in names:
        on = [d for d in docs.values() if d["meta"].get("id") and d["rel"] != me_path and s in records_systems(d)]
        open_ = [_line(d) for d in on if d["meta"].get("status") == "open"]
        page = f"wiki/systems/{s}.md"
        systems[s] = {"page": page if page in docs and page != me_path else None,
                      "open": open_[:limit], "open_total": len(open_), "other": len(on) - len(open_)}
    return {"page": _line(me), "chain": chain, "replaces": replaces, "links": links[:limit],
            "cited_by": cited[:limit], "counts": {"links": len(links), "cited_by": len(cited)}, "systems": systems}


def records_systems(d):
    v = d["meta"].get("systems") or []
    return [str(x) for x in (v if isinstance(v, list) else [v])]


def format(d, get_hint="acme-kb get REF"):
    """One line per related page; a page already shown is named again only by its id."""
    def name(x):
        return x["id"] or x["path"]

    def row(x):
        s = x["summary"] if len(x["summary"]) <= SUMMARY_CHARS else x["summary"][:SUMMARY_CHARS].rstrip() + "..."
        return f"  {name(x)} · " + (f"[{x['status']}] " if x["status"] else "") + s

    p = d["page"]
    lines = [f"{p['path']} · " + (f"[{p['status']}] " if p["status"] else "") + p["summary"]]
    seen = {name(p)}

    def group(title, items, more=0):
        new = [x for x in items if name(x) not in seen]
        again = [name(x) for x in items if name(x) in seen]
        lines.append(title + ":")
        lines.extend(row(x) for x in new)
        seen.update(name(x) for x in new)
        if again:
            lines.append("  above: " + ", ".join(again))
        if more > 0:
            lines.append(f"  ({more} more)")

    if d["chain"]:
        group(f"superseded: the current one is {d['chain'][-1]['id']}", d["chain"])
    if d["replaces"]:
        group("replaces", d["replaces"])
    for key, title in (("links", "links to"), ("cited_by", "cited by")):
        if d[key]:
            group(f"{title} ({d['counts'][key]})", d[key], d["counts"][key] - len(d[key]))
    for s, v in d["systems"].items():
        if v["open"] or v["page"]:
            head = f"system {s}" + (f", page {v['page']}" if v["page"] else "") + f" · {v['open_total']} other open, {v['other']} closed"
            group(head, v["open"], v["open_total"] - len(v["open"]))
    lines.append(f"read one: {get_hint}")
    return "\n".join(lines)
