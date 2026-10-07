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
- `index.md` and `index-full.md` are generated locally by `acme-kb gen-index` and are not
  tracked. `index.md` is a short map: one line per system with its page and how many records
  name it, how many of those are open. `index-full.md` lists every record with its summary.
- `.queries/` is your local search log, not tracked either (see below).

## Before you answer a question about our systems

1. `acme-kb sync`, then `acme-kb search <two or three words>`, with `--in-repo <repo>` when
   the question is about one repository (pages that name no repo, like wiki pages, stay;
   `--status` with words keeps them the same way, `--type` lists that type only).
   Results are ranked and ten lines long (`--limit N`, 0 for all). Lines after
   `-- not every term matched --` hold only some of the words: nearby, not a match.
   Without words, search lists every record the filters pass.
2. Search found nothing useful: open `index.md`, pick the system, `acme-kb search <system>`.
3. Read two or three records, not more.
4. Take exact values (versions, flags, limits) from `raw/`, not from a summary.
5. End the answer with a footer:
   `source: <id> (<confidence>) · <wiki page> (<updated>) · owner: <owner>`
   If nothing was found, say so. Do not answer from general knowledge as if it were ours.

## Writing a record

- One file per record, created with `acme-kb new <kind> "<summary>"`. Never append to a
  shared file: two merge requests that append to the same file always conflict.
- `summary` is one sentence a colleague can act on without opening the file.
- `aliases: [a, b]` is optional on any record or page: the other names people search by
  when the summary does not hold them. Search weighs them like the summary.
- `confidence: verified` only if somebody observed it; otherwise `assumed`. Verified
  needs `evidence`: a commit, a merge request or a file path.
- `expires` defaults to 180 days. Knowledge about infrastructure rots.
- No secrets, tokens, internal host names or personal data. Ever.
- Ask the human before you write. Then `acme-kb capture <id>` and open a pull request.

## Search, for scripts and for the record

- `acme-kb search --json` prints the same results as records (path, kind, match, id, status,
  confidence, summary, systems, repos, aliases, dates). The contract is
  `tools/acme_kb/search.schema.json`; `schema_version` changes only when a field is removed,
  renamed or changes meaning.
- Every search with words appends one line to `.queries/YYYY-MM.jsonl` in the checkout. It
  stays on your laptop; `ACME_KB_NO_QUERY_LOG=1` switches it off. `acme-kb queries` reports
  the searches, how many had no full match, how many were rephrased within five minutes, and
  the top misses: candidates for an alias or a new page.

## Changing a record

Status changes (`open` to `fixed`, `accepted` to `superseded`) go the same way a record
was born: an edit, `updated` set to today, a pull request, one reviewer.

## The gate

`./scripts/check.sh` must pass: the schema (including `aliases` as a list), dead `[[links]]`,
required sections of system pages, tests, and no generated file tracked. An expired open
record is a warning, not an error.
