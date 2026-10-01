---
type: wiki
summary: "The GitOps server that deploys every workload; people log in through SSO, tools use a local read-only account"
owner: platform-team
sources: [raw/2026-09-16-gitops-token-notes]
updated: 2026-09-16
---
## What it is

The GitOps server watches the config repositories and keeps the clusters in the state
they describe. There is one instance for prod and one for test.

## How we run it

- People authenticate through SSO. Their session lasts 24 hours and the CLI renews it.
- Tools that need a token that does not expire use the local account `readonly-bot`,
  which can only read.
- Agents talk to it through a read-only MCP server, one per environment.

## Traps

- An SSO user can never hold a long-lived API token, see
  [[memory/findings/F-2026-09-16-001]].
- A rollout that looks stuck is usually a failing readiness probe, see
  [[memory/incidents/I-2026-09-25-001]].
