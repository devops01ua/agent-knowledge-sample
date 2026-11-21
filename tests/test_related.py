import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

from acme_kb import read, related, search  # noqa: E402


class ReadRelatedTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "kb"
        shutil.copytree(REPO, self.root, symlinks=True, ignore=shutil.ignore_patterns(".git", "eval"))

    def test_get_gives_working_fields_not_the_file(self):
        d = read.get(self.root, "F-2026-09-20-001")
        self.assertEqual(d["fields"]["status"], "open")
        self.assertNotIn("evidence", d["fields"])
        self.assertIn("fix: The installer copies", read.format(d))

    def test_get_page_outline_then_section(self):
        self.assertIn("Traps", read.get(self.root, "agent-tooling")["outline"])
        d = read.get(self.root, "agent-tooling", sections=["traps"])
        self.assertEqual(d["sections"][0][0], "Traps")
        self.assertEqual(read.get(self.root, "agent-tooling", sections=["nope"])["missing"], ["section: nope"])

    def test_get_refuses_paths_outside(self):
        with self.assertRaises(read.NotFound):
            read.get(self.root, "../AGENTS")

    def test_related_follows_the_chain_and_backlinks(self):
        d = related.related(self.root, "D-2026-09-16-001")
        self.assertEqual([x["id"] for x in d["chain"]], ["D-2026-11-10-001"])
        self.assertEqual(sorted(x["id"] for x in d["cited_by"]), ["D-2026-11-10-001", "F-2026-09-20-001"])
        text = related.format(d)
        self.assertIn("the current one is D-2026-11-10-001", text)
        self.assertEqual(text.count("D-2026-11-10-001 ·"), 1)  # shown once, named again as `above`

    def test_related_system_page_lists_its_open_records(self):
        d = related.related(self.root, "agent-tooling")
        self.assertEqual(sorted(x["id"] for x in d["systems"]["agent-tooling"]["open"]), ["F-2026-09-20-001", "F-2026-11-12-001"])

    def test_fuse_keeps_full_matches_first_and_votes_the_rest(self):
        docs = [{"rel": r} for r in ("a", "b", "c", "d")]
        full, rest = search.fuse(docs, [docs[0]], [docs[1], docs[2]], ["d", "c", "a"])
        self.assertEqual(full, [docs[0]])
        self.assertEqual([d["rel"] for d in rest], ["c", "b", "d"])  # c: in both lists; b: words #1; d: meaning #1


if __name__ == "__main__":
    unittest.main()
