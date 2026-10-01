# agent-knowledge-sample

A sample **shared memory for a team's coding agents**: markdown in git, review through
pull requests, no database and no SaaS. What one engineer's agent found today, every
engineer's agent can read tomorrow morning.

It is the companion repo of the article "The Chronicle of the Tower, or How Our Coding
Agents Learned to Remember", and the second half of
[agent-plugins-sample](https://github.com/devops01ua/agent-plugins-sample), which holds
the tools the agents work with. Everything here is a sample: the systems, names and
records are made up.

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
scripts/check.sh     the gate, also run in CI
```

## Try it

```bash
uv tool install git+https://github.com/devops01ua/agent-knowledge-sample.git
acme-kb setup                      # clone to ~/.acme-knowledge, link the skills
acme-kb search token               # exact-word search over every record
acme-kb search rollout --type incident
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
acme-kb search gitops token                    # 2. searches by exact words
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
| `acme-kb search <words> [--type] [--status] [--in-repo]` | every word must occur; no synonyms, no ranking |
| `acme-kb new finding\|decision\|incident "<summary>"` | a record from its template with the next id |
| `acme-kb validate` | schema, dead links, required sections; expired open records as warnings |
| `acme-kb capture <id>` | validate that record and commit it on `capture/<id>` |
| `acme-kb gen-index` | write a local `index.md` (not tracked) |
| `acme-kb init-repo <path>` | add an `AGENTS.md` compass to a code repository |

## Rules worth copying

- One file per record. A shared file that everyone appends to is a merge conflict factory.
- `confidence: verified` only for what somebody observed, and it needs evidence.
- Every finding expires (180 days by default). An expired open record is a warning.
- The agent asks before it writes, and a human reviews every record.
- The generated index stays out of git.

## Honest limits

- The search matches exact words: `nightmode` will not find `night mode`.
- The gate checks the form. Contradictions between pages are found by a person with an
  agent, once a month (the `lint` skill).
- `setup` links skills; a tool that ignores symlinked skills needs copies instead.

## License

MIT
