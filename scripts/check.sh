#!/usr/bin/env bash
# The gate: runs locally and in CI, needs only python and git.
set -uo pipefail
cd "$(dirname "$0")/.."
fail=0
run() { local label="$1"; shift; echo "-- ${label}"; if "$@"; then echo "ok   ${label}"; else echo "FAIL ${label}"; fail=1; fi; }
run "records match the schema" env PYTHONPATH=tools python3 -m acme_kb --repo . validate
run "tests" python3 -m unittest discover -s tests -q
run "CLAUDE.md is a symlink to AGENTS.md" sh -c 'test -L CLAUDE.md && [ "$(readlink CLAUDE.md)" = AGENTS.md ]'
run "generated files are not tracked" sh -c '[ -z "$(git ls-files index.md index-full.md .queries)" ]'
if [ "$fail" -eq 0 ]; then echo "ALL CHECKS PASSED"; else echo "SOME CHECKS FAILED"; fi
exit "$fail"
