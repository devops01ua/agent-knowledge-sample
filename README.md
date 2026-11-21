# agent-knowledge-sample

A sample **shared memory for a team's coding agents**: markdown in git, review through
pull requests, no database and no SaaS. What one engineer's agent found today, every
engineer's agent can read tomorrow morning.

It is the companion repo of three articles: "The Chronicle of the Tower" (tag `article-1`),
"The Chronicle Learns to Search" (`article-2`) and "The Knowledge Repo Gets a Front Door"
(`article-3`: `get`, `list`, `related`, ranking by meaning, an MCP server and the eval). It is the second half of
[agent-plugins-sample](https://github.com/devops01ua/agent-plugins-sample), which holds
the tools the agents work with. Everything here is a sample: the systems, names and
records are made up.

## How it fits together

An interactive map of the marketplace, the laptop, this repo and the project repos, with the main flows step by step: [docs/architecture.html](https://devops01ua.github.io/agent-knowledge-sample/architecture.html) (open the file locally if the page is not published yet).

## What is inside

```text
AGENTS.md            the schema: rules for an agent that edits this repo (CLAUDE.md links to it)
raw/                 sources as they came in, never edited
wiki/                pages about systems, compiled from raw/ and kept current by agents
memory/findings/     what turned out to be true, with evidence
memory/decisions/    choices made, with the options that were rejected
memory/incidents/    what broke, why, what fixed it
templates/           one template per record type, plus the compass for code repos
.agents/skills/      five skills: knowledge, capture, ingest, lint, start-task
tools/acme_kb/       the acme-kb CLI (standard library only)
mcp/server.py        the same functions as four MCP tools (needs the `mcp` package)
eval/                questions with ground truth from the repo, and a harness that asks a headless agent
scripts/check.sh     the gate, also run in CI
```

## Try it

```bash
uv tool install git+https://github.com/devops01ua/agent-knowledge-sample.git
acme-kb setup                      # clone to ~/.acme-knowledge, link the skills
acme-kb search gitops token        # ranked search over every record
acme-kb search rollout --type incident
acme-kb search token --json        # the same results for a script
```

Or without installing, from a clone:

```bash
PYTHONPATH=tools python3 -m acme_kb search token
```

With Claude Code, the `acme-knowledge` plugin of the sample marketplace does the setup
for you and reminds you to capture after infrastructure work:

```bash
claude plugin marketplace add https://github.com/devops01ua/agent-plugins-sample.git
claude plugin install acme-knowledge@acme
```

## The path of one finding

```bash
acme-kb sync                                   # 1. the agent pulls the fresh knowledge
acme-kb search gitops token                    # 2. ranked search, ten lines
#                                                3. reads two or three records and answers with a footer:
#   source: F-2026-09-16-001 (verified) · wiki/systems/gitops-server (2026-09-16) · owner: platform-team
acme-kb new finding "One sentence you can act on"   # 4. after the human says yes
acme-kb validate                               # 5. the schema, links, sections
acme-kb capture F-2026-10-01-001               # 6. one record, one branch, one commit
git push -u origin capture/F-2026-10-01-001    # 7. a pull request, one reviewer
```

The reviewer checks four things: the summary can be acted on, there is evidence, the
confidence is honest, there are no secrets.

## Commands

| Command | What it does |
| --- | --- |
| `acme-kb setup` | clone or update the checkout and link the skills into `~/.claude/skills` and `~/.agents/skills` |
| `acme-kb sync` | `git pull --ff-only` in the checkout |
| `acme-kb search [<words>] [--type] [--status] [--in-repo] [--limit N] [--json]` | records holding every word first, best first (BM25), then those holding some; without words, the filtered list |
| `acme-kb search <words> --kb` | also rank by meaning with a managed knowledge base (`ACME_KB_ID`, aws CLI); keywords only when it is missing |
| `acme-kb get <id\|path\|system> [--fields a,b] [--section H]` | a record's working fields or a page's outline and sections, not the whole file |
| `acme-kb list [--type] [--status] [--in-repo] [--system]` | records with their summaries, instead of opening an index |
| `acme-kb related <ref> [--limit N]` | supersede chain, links, cited by, other open records on the same systems |
| `acme-kb kb-export <dir>` | every record as knowledge-base documents (whole + digest) with `.metadata.json` |
| `acme-kb mcp` | how to reach the same functions over MCP |
| `acme-kb queries [--days N]` | report from the local search log: misses, rephrased searches |
| `acme-kb new finding\|decision\|incident "<summary>"` | a record from its template with the next id |
| `acme-kb validate` | schema, dead links, required sections; expired open records as warnings |
| `acme-kb capture <id>` | validate that record and commit it on `capture/<id>` |
| `acme-kb gen-index` | write a local `index.md` (system map) and `index-full.md` (every record), not tracked |
| `acme-kb init-repo <path>` | add an `AGENTS.md` compass to a code repository |

## Rules worth copying

- One file per record. A shared file that everyone appends to is a merge conflict factory.
- `confidence: verified` only for what somebody observed, and it needs evidence.
- Every finding expires (180 days by default). An expired open record is a warning.
- The agent asks before it writes, and a human reviews every record.
- The generated index and the search log stay out of git.
- A search that missed is a signal: `acme-kb queries` lists the misses, and the answer is an
  `aliases` entry on the page that should have been found, or a new page. A search that was
  rephrased until another one found a page is the same signal, even when the first try had results.

## How search ranks

Every record is put in an in-memory SQLite FTS5 table on each call (the repo is small, so
there is no index file to go stale). A record that holds every word comes first, ordered by
BM25, with the path, id, summary, systems and aliases weighing more than the body. Records
that hold only some of the words follow after `-- not every term matched --`. Without FTS5
in your Python's SQLite the same records come back, ordered by how many words they hold.

### With a ranking by meaning (`--kb`)

Records holding every word stay first, in BM25 order. The rest - partial keyword matches and
what the knowledge base found - is a vote:

```text
score = 1/(60 + place by words) + 0.5/(60 + place by meaning)
```

60 is the usual reciprocal-rank constant: places 1 and 2 differ little, so agreement between
the two lists decides. The meaning vote weighs half: at 1.0 a page weak in both lists jumped
over a strong keyword match. `acme-kb kb-export` writes the documents; upload them to the KB's
bucket and run an ingestion job in CI. The repo path travels in the metadata, so an answer
from the KB always leads back to the reviewed file.

## MCP

```bash
pip install -r mcp/requirements.txt
python mcp/server.py --stdio                          # one agent, this laptop
ACME_KB_MCP_TOKEN=... python mcp/server.py --http     # a shared server, bearer token
```

Four tools over the same functions: `kb_search` (terms as a list, enums for type and status),
`kb_get`, `kb_list`, `kb_related`. Answers are `key: value` lines, not JSON: for the same
answers indented JSON cost a third more tool output. Every call logs one JSON line (tool,
caller, parameters, paths, bytes, latency), never page text. Writes do not go through it:
a record is still a branch and a pull request.

## Eval

`eval/questions.py` builds relation questions with answers read straight from the files
(supersede chains, backlinks, open records per system). `eval/run.py grep|mcp|mcp+` asks a
headless Claude Code each question with the clone only, the MCP tools without `kb_related`,
and with it, and prints what was found, tool calls, bytes of tool output, tokens and cost.
On a sample this small the numbers say little; run it on your own repo.

## Honest limits

- Without `--kb` search knows words and word forms, not meaning: `nightmode` will not find
  `night mode` unless a page lists it in `aliases`.
- The MCP server has one shared token; per-person identity is up to your gateway.
- The gate checks the form. Contradictions between pages are found by a person with an
  agent, once a month (the `lint` skill).
- `setup` links skills; a tool that ignores symlinked skills needs copies instead.

## License

MIT
