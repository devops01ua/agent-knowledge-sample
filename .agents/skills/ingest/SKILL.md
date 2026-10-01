---
name: ingest
description: Bring an external source into the knowledge repo and distil it into a wiki
  page. Use when the user shares a vendor doc, a changelog, release notes or a
  post-mortem worth keeping, or says ingest this, add this to the wiki.
---

# Ingest

1. Save the source under `raw/` as `<date>-<slug>.md`, unchanged.
2. Find the wiki pages it touches (`acme-kb search`). Update them, or create a page
   under `wiki/systems/` with the sections "What it is", "How we run it", "Traps".
3. List the source in the page's `sources` and set `updated` to today.
4. Run `acme-kb validate`, then open a pull request.
