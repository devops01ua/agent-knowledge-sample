---
type: wiki
summary: "The coding agents the team uses and how they reach shared knowledge: skills on the laptop, the CLI, and the MCP server"
owner: platform-team
updated: 2026-11-12
aliases: [agents, coding agents, mcp]
---
# Agent tooling

## What it is
Four coding agent tools on laptops and one hosted agent that investigates alerts. All of
them read the knowledge repo: the laptop tools through skills and `acme-kb`, every agent
through the MCP server in `mcp/` when it is configured.

## How we run it
- Skills come from the plugin marketplace; `acme-kb setup` links the shared ones.
- The MCP server reads a clone of main and answers `kb_search`, `kb_get`, `kb_list`, `kb_related`.
- One instruction file per repo: [[memory/decisions/D-2026-11-10-001]].

## Traps
- One tool ignores symlinked skills: [[memory/findings/F-2026-09-20-001]].
- MCP tools listed by name only are not called until loaded: [[memory/findings/F-2026-11-12-001]].
