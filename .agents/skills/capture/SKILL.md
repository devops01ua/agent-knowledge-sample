---
name: capture
description: Record something the team learned as a finding, a decision or an incident.
  Use when the user says capture, remember this for the team, write this down, or
  after a session found a quirk, made a choice with rejected options, or worked an
  incident.
---

# Capture

1. Say in one sentence what you would record and ask the user for a yes.
2. Check it is not there already: `acme-kb search <two or three words>`. Only lines above
   `-- not every term matched --` hold every word.
3. `acme-kb new finding "<summary>"` (or `decision`, `incident`).
4. Fill every field. Add `aliases: [..]` when people would search by a name the summary
   does not hold. `confidence: verified` only if it was observed in this session;
   add the evidence (commit, pull request, file path).
5. Remove secrets, tokens, host names and personal data.
6. `acme-kb capture <id>`, push the branch and open a pull request.
