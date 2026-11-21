"""Ask a headless coding agent the same questions with different tools, and count what it cost.

    python3 eval/run.py MODE [reps]
    MODE: grep   - the clone only (Read, Grep, Glob)
          mcp    - the MCP server only, without kb_related
          mcp+   - the MCP server only, with kb_related

Needs Claude Code (`claude`) and the server's dependencies (mcp/requirements.txt). The server runs
over stdio from this clone, so every mode reads the same files. Writes eval/runs/<mode>-<id>-<rep>.json
and prints a summary: share of expected ids found, tool calls, bytes of tool output, input tokens, cost.

Two traps we hit, both handled here:
- an installed skill leaked into a mode that should not have it: `--disallowedTools Skill`;
- Claude Code lists MCP tools by name only until they are loaded, and an agent that sees Grep
  greps instead: the prompt tells it to load the tools first.
"""
import json
import os
import statistics as st
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODE = sys.argv[1]
REPS = int(sys.argv[2]) if len(sys.argv) > 2 else 2
MODEL = os.environ.get("EVAL_MODEL", "haiku")
Q = json.load(open(ROOT / "eval" / "questions.json"))
TOOLS = {"grep": [], "mcp": ["kb_search", "kb_get", "kb_list"], "mcp+": ["kb_search", "kb_get", "kb_list", "kb_related"]}[MODE]
OUT = ROOT / "eval" / "runs"
OUT.mkdir(exist_ok=True)


def run(q, rep):
    path = OUT / f"{MODE}-{q['id']}-{rep}.json"
    if path.exists():
        return json.loads(path.read_text())
    how = (f"The knowledge repo is at {ROOT}; read its files." if MODE == "grep" else
           "Use only the acme-kb MCP tools; load them first if they are listed by name only. There is no checkout to read.")
    prompt = f"Question from an engineer: {q['q']}\nAnswer in at most 8 lines with ids and paths.\n{how}"
    with tempfile.TemporaryDirectory() as cwd:
        cmd = ["claude", "-p", prompt, "--model", MODEL, "--output-format", "stream-json", "--verbose",
               "--max-turns", "25", "--disallowedTools", "Skill", "--strict-mcp-config"]
        if MODE == "grep":
            cmd += ["--add-dir", str(ROOT), "--allowedTools", "Read,Grep,Glob"]
        else:
            cfg = {"mcpServers": {"acme-kb": {"command": sys.executable, "args": [str(ROOT / "mcp" / "server.py"), "--stdio"],
                                              "env": {"ACME_KNOWLEDGE_HOME": str(ROOT)}}}}
            Path(cwd, "mcp.json").write_text(json.dumps(cfg))
            cmd += ["--mcp-config", f"{cwd}/mcp.json", "--allowedTools", ",".join(f"mcp__acme-kb__{t}" for t in TOOLS)]
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=900)
    calls, tool_bytes, res = 0, 0, {}
    for line in p.stdout.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") == "assistant":
            calls += sum(1 for c in e["message"]["content"] if c.get("type") == "tool_use" and c["name"] != "ToolSearch")
        elif e.get("type") == "user":
            for c in e["message"].get("content", []):
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    cc = c.get("content")
                    tool_bytes += len(cc.encode()) if isinstance(cc, str) else sum(len((x.get("text") or "").encode()) for x in cc or [])
        elif e.get("type") == "result":
            res = e
    u, answer = res.get("usage", {}), res.get("result") or ""
    rec = {"mode": MODE, "id": q["id"], "kind": q["kind"], "rep": rep,
           "found": sum(x in answer or x.rsplit("/", 1)[-1] in answer for x in q["expected"]) / len(q["expected"]),
           "calls": calls, "tool_bytes": tool_bytes,
           "input_tokens": sum(u.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")),
           "cost": res.get("total_cost_usd") or 0, "answer": answer[:600]}
    path.write_text(json.dumps(rec, indent=1))
    return rec


with ThreadPoolExecutor(4) as pool:
    recs = list(pool.map(lambda a: run(*a), [(q, r) for q in Q for r in range(REPS)]))
m = lambda k: st.mean(r[k] for r in recs)
print(f"{MODE}: n={len(recs)} found={m('found'):.2f} calls={m('calls'):.1f} "
      f"tool_KB={m('tool_bytes')/1024:.1f} input_tokens={m('input_tokens'):.0f} cost=${m('cost'):.4f}")
