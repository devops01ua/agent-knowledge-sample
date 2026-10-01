# AGENTS.md - rules for editing this knowledge repo

This repo is the shared memory of a team's coding agents. Whatever agent you are, you are
an editor here, and these are the house rules. `CLAUDE.md` is a symlink to this file.

## Layout

- `raw/` - sources as they came in (vendor docs, post-mortems, notes). Never edit them.
- `wiki/` - pages about our systems, compiled from `raw/` and kept current by agents.
- `memory/` - what the team learned in practice:
  - `findings/` - something that turned out to be true about a system, with evidence
  - `decisions/` - a choice we made, with the options we rejected
  - `incidents/` - what broke, why, and what fixed it
- `templates/` - one template per record type, plus the compass for code repositories.
- `index.md` is generated locally by `acme-kb gen-index` and is not tracked.

## Before you answer a question about our systems

1. `acme-kb sync`, then `acme-kb search <words>`. Search is exact words, so try the
   shortest distinctive word first.
2. Read two or three records, not more.
3. Take exact values (versions, flags, limits) from `raw/`, not from a summary.
4. End the answer with a footer:
   `source: <id> (<confidence>) · <wiki page> (<updated>) · owner: <owner>`
   If nothing was found, say so. Do not answer from general knowledge as if it were ours.

## Writing a record

- One file per record, created with `acme-kb new <kind> "<summary>"`. Never append to a
  shared file: two merge requests that append to the same file always conflict.
- `summary` is one sentence a colleague can act on without opening the file.
- `confidence: verified` only if somebody observed it; otherwise `assumed`. Verified
  needs `evidence`: a commit, a merge request or a file path.
- `expires` defaults to 180 days. Knowledge about infrastructure rots.
- No secrets, tokens, internal host names or personal data. Ever.
- Ask the human before you write. Then `acme-kb capture <id>` and open a pull request.

## Changing a record

Status changes (`open` to `fixed`, `accepted` to `superseded`) go the same way a record
was born: an edit, `updated` set to today, a pull request, one reviewer.

## The gate

`./scripts/check.sh` must pass: the schema, dead `[[links]]`, required sections of system
pages, tests. An expired open record is a warning, not an error.
