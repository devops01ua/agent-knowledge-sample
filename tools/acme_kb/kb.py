"""An optional ranking by meaning from a managed knowledge base (Amazon Bedrock Knowledge Bases
over an S3 Vectors index in the article). Nothing account-specific lives in the repo: the KB id,
region and profile come from the environment, and AWS is reached through the aws CLI, so the
CLI stays standard library only. When the CLI, the profile or the KB is missing, search goes on
with keywords and says so.

ACME_KB_ID, ACME_KB_REGION (default eu-central-1), ACME_KB_PROFILE (optional), ACME_KB_TOP (20).

`export` writes the corpus as KB documents: per record the whole record and a short digest, each
with a `.metadata.json` that keeps the repo path, so an answer from the KB always leads back to
the reviewed file in git. Upload them to the KB's bucket and start an ingestion job in CI.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

from . import records

META_MAX = 900  # the KB allows about 1 KB of custom metadata per document


class Unavailable(RuntimeError):
    pass


def retrieve(text):
    kb_id = os.environ.get("ACME_KB_ID")
    if not kb_id or not shutil.which("aws"):
        raise Unavailable("no ACME_KB_ID or no aws CLI")
    cmd = ["aws", "bedrock-agent-runtime", "retrieve", "--knowledge-base-id", kb_id,
           "--region", os.environ.get("ACME_KB_REGION", "eu-central-1"),
           "--retrieval-query", json.dumps({"text": text}),
           "--retrieval-configuration", json.dumps({"vectorSearchConfiguration": {"numberOfResults": int(os.environ.get("ACME_KB_TOP", "20"))}}),
           "--output", "json"]
    if os.environ.get("ACME_KB_PROFILE"):
        cmd += ["--profile", os.environ["ACME_KB_PROFILE"]]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if out.returncode:
        raise Unavailable(out.stderr.strip().splitlines()[-1] if out.stderr.strip() else "aws CLI failed")
    paths = []
    for r in json.loads(out.stdout).get("retrievalResults", []):
        p = (r.get("metadata") or {}).get("path")
        if p and p not in paths:  # a record's digest and its whole text are one result
            paths.append(p)
    return paths


def export(root, out):
    root, out = Path(root), Path(out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    n = 0
    for rec in records.load(root):
        rel = rec.path.relative_to(root).as_posix()
        meta = {"path": rel, "type": rec.kind or "wiki", "status": str(rec.meta.get("status") or "none")}
        systems = [str(s) for s in (rec.meta.get("systems") or [])][:8]
        while systems and len(json.dumps({**meta, "systems": systems})) > META_MAX:
            systems.pop()
        if systems:
            meta["systems"] = systems
        name = rel.replace("/", "__")
        digest = "\n".join(f"{k}: {rec.meta[k]}" for k in ("id", "summary", "symptom", "decision") if rec.meta.get(k))
        for suffix, text in (("__00.md", rec.path.read_text()), ("__digest.md", digest)):
            if text:
                (out / (name + suffix)).write_text(text)
                (out / (name + suffix + ".metadata.json")).write_text(json.dumps({"metadataAttributes": meta}))
                n += 1
    return n
