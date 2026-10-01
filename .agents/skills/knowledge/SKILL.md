---
name: knowledge
description: Look things up in the team's shared knowledge before acting. Use whenever
  the task touches infrastructure, deploys, CI, an incident, a vendor quirk, or a
  question like "how do we do X here", "has anyone hit this", "what is our convention".
---

# Knowledge

1. Run `acme-kb sync`.
2. Run `acme-kb search <word>` with the shortest distinctive word. The search matches
   exact words; if nothing comes back, try another word before giving up.
3. Read at most three records. Take exact values from `raw/`.
4. Answer, then add the footer:
   `source: <id> (<confidence>) · <wiki page> (<updated>) · owner: <owner>`
5. If nothing relevant exists, say "nothing in the knowledge repo about this" and
   answer from general knowledge, clearly marked as such.
