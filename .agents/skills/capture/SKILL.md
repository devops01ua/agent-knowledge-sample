---
name: capture
description: Record something the team learned as a finding, a decision or an incident.
  Use when the user says capture, remember this for the team, write this down, or
  after a session found a quirk, made a choice with rejected options, or worked an
  incident.
---

# Capture

1. Say in one sentence what you would record and ask the user for a yes.
2. `acme-kb new finding "<summary>"` (or `decision`, `incident`).
3. Fill every field. `confidence: verified` only if it was observed in this session;
   add the evidence (commit, pull request, file path).
4. Remove secrets, tokens, host names and personal data.
5. `acme-kb capture <id>`, push the branch and open a pull request.
