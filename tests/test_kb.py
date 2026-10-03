import contextlib
import datetime as dt
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

from acme_kb import cli, records  # noqa: E402


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(list(argv))
    return code, out.getvalue()


class Sandbox(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve() / "kb"
        shutil.copytree(REPO, self.root, symlinks=True,
                        ignore=shutil.ignore_patterns(".git", "__pycache__", "index.md", "index-full.md", ".queries"))
        self.finding = self.root / "memory" / "findings" / "F-2026-09-16-001.md"

    def edit(self, path, old, new):
        text = path.read_text()
        self.assertIn(old, text)
        path.write_text(text.replace(old, new))


class SchemaTest(Sandbox):
    def test_the_repo_itself_is_valid(self):
        self.assertEqual(records.check(REPO, today=dt.date(2026, 10, 1)), ([], []))

    def test_missing_field_and_bad_status(self):
        self.edit(self.finding, "status: fixed", "status: done")
        self.edit(self.finding, 'root_cause: "API keys', 'cause: "API keys')
        errors, _ = records.check(self.root)
        self.assertTrue(any("missing field root_cause" in e for e in errors))
        self.assertTrue(any("status must be one of" in e for e in errors))

    def test_verified_needs_evidence(self):
        self.edit(self.finding, "evidence: [platform a1b2c3d, configs/gitops/server.yaml]", "evidence: []")
        errors, _ = records.check(self.root)
        self.assertTrue(any("verified needs evidence" in e for e in errors))

    def test_dead_link(self):
        self.edit(self.finding, "[[wiki/systems/gitops-server]]", "[[wiki/systems/nope]]")
        errors, _ = records.check(self.root)
        self.assertTrue(any("dead link [[wiki/systems/nope]]" in e for e in errors))

    def test_system_page_needs_its_sections(self):
        self.edit(self.root / "wiki" / "systems" / "gitops-server.md", "## Traps", "## Gotchas")
        errors, _ = records.check(self.root)
        self.assertTrue(any("lacks the section '## Traps'" in e for e in errors))

    def test_expired_open_record_is_a_warning(self):
        errors, warnings = records.check(self.root, today=dt.date(2027, 6, 1))
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 1)  # the open finding; the fixed one is not reported
        self.assertIn("F-2026-09-20-001", warnings[0])


class CliTest(Sandbox):
    def test_search_with_filters(self):
        _, out = run("--repo", str(self.root), "search", "token")
        self.assertIn("F-2026-09-16-001", out)
        _, out = run("--repo", str(self.root), "search", "symlinks", "--status", "open")
        self.assertIn("F-2026-09-20-001", out)
        _, out = run("--repo", str(self.root), "search", "sym-links")
        self.assertIn("no records match", out)
        _, out = run("--repo", str(self.root), "search", "rollout", "--type", "incident")
        self.assertIn("I-2026-09-25-001", out)
        self.assertNotIn("F-2026", out)

    def test_new_record_gets_the_next_id_and_a_180_day_expiry(self):
        today = dt.date.today()
        _, first = run("--repo", str(self.root), "new", "finding", "First thing")
        _, second = run("--repo", str(self.root), "new", "finding", "Second thing")
        self.assertTrue(first.strip().endswith(f"F-{today.isoformat()}-001.md"))
        self.assertTrue(second.strip().endswith(f"F-{today.isoformat()}-002.md"))
        rec = records.parse(self.root / first.strip())
        self.assertEqual(rec.meta["summary"], "First thing")
        self.assertEqual(rec.meta["expires"], (today + dt.timedelta(days=180)).isoformat())
        code, out = run("--repo", str(self.root), "validate")
        self.assertEqual(code, 1)  # a fresh template is not a finished record
        self.assertIn("missing field symptom", out)

    def test_capture_commits_one_record_on_its_own_branch(self):
        git = lambda *a: subprocess.run(["git", "-C", str(self.root), *a], check=True, capture_output=True, text=True)
        git("init", "-q", "-b", "main")
        git("-c", "user.name=t", "-c", "user.email=t@example.com", "add", "-A")
        git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "base")
        _, out = run("--repo", str(self.root), "new", "decision", "Use one gate script")
        path = self.root / out.strip()
        rid = path.stem
        self.edit(path, 'context: ""', 'context: "Two scripts drifted"')
        self.edit(path, 'decision: ""', 'decision: "One script, CI calls it"')
        self.edit(path, "rejected: []", "rejected: [two scripts]")
        self.edit(path, "repos: []", "repos: [agent-knowledge]")
        os.environ.update(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
                          GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
        _, out = run("--repo", str(self.root), "capture", rid)
        self.assertIn(f"capture/{rid}", out)
        self.assertEqual(git("branch", "--show-current").stdout.strip(), f"capture/{rid}")
        self.assertEqual(git("show", "--name-only", "--format=", "HEAD").stdout.strip(), f"memory/decisions/{rid}.md")

    def test_gen_index_and_init_repo(self):
        _, out = run("--repo", str(self.root), "gen-index")
        self.assertIn("index-full.md: 5 records", out)
        self.assertIn("F-2026-09-16-001", (self.root / "index-full.md").read_text())
        target = self.root.parent / "some-code-repo"
        target.mkdir()
        run("--repo", str(self.root), "init-repo", str(target))
        self.assertIn("## Traps", (target / "AGENTS.md").read_text())

    def test_setup_links_every_skill(self):
        target = self.root.parent / "skills"
        (target / "lint").mkdir(parents=True)  # something the user already has stays
        with contextlib.redirect_stdout(io.StringIO()):
            cli.link_skills(self.root, [target])
        names = sorted(p.name for p in target.iterdir())
        self.assertEqual(names, ["capture", "ingest", "knowledge", "lint", "start-task"])
        self.assertTrue((target / "knowledge").is_symlink())
        self.assertFalse((target / "lint").is_symlink())


if __name__ == "__main__":
    unittest.main()
