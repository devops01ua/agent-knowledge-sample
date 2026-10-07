---
name: lint
description: Find rot in the knowledge repo. Use for the monthly check, when asked to
  review stale findings, find contradictions, or after a batch of ingests.
---

# Lint

1. `acme-kb validate`: fix errors, list the expiry warnings.
2. For each expired open finding: is it fixed, still true, or obsolete? Propose the
   new status, do not change it silently.
3. Read the pages changed in the last month and look for contradictions between them.
4. `acme-kb queries` for the misses of the last month: give each an `aliases` entry on the
   page that answers it, or list it as a suggested page. A line `query -> page` is a search
   somebody rephrased until that page came up: read the page, and if the first words name
   it, add them as `aliases`; if the first query carried a filter, check the filter.
5. Open one pull request with the fixes and a list of what needs a human decision.
