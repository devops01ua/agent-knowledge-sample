# Eval

```bash
PYTHONPATH=tools python3 eval/questions.py > eval/questions.json
python3 eval/run.py grep      # the clone only
python3 eval/run.py mcp       # MCP tools without kb_related
python3 eval/run.py mcp+      # with kb_related
```

Ground truth comes from outside the tool under test: frontmatter and links read straight from
the files. Runs land in `eval/runs/` (not tracked). The model is `EVAL_MODEL` (haiku by default).

Traps this harness already handles:

- an installed skill leaking into a mode that should not have it (`--disallowedTools Skill`);
- an agent that sees MCP tools by name only and greps instead (the prompt says to load them;
  see memory/findings/F-2026-11-12-001.md).
