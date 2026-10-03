import datetime as dt
import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_kb import REPO, Sandbox, run  # noqa: E402
from acme_kb import cli, querylog, records, search  # noqa: E402

SCHEMA = json.loads((REPO / "tools" / "acme_kb" / "search.schema.json").read_text())
TYPES = {"object": dict, "array": list, "string": str, "integer": int, "null": type(None)}
T0 = datetime(2026, 10, 3, 9, 0, tzinfo=timezone.utc)
NO_LOG = {"ACME_KB_NO_QUERY_LOG": "1"}


def problems(schema, value, at="$"):
    """The part of JSON Schema the contract uses: type, enum, const, required, properties,
    additionalProperties false, items. Enough to keep the output and the schema file in step."""
    out = []
    types = schema.get("type")
    if types:
        types = [types] if isinstance(types, str) else types
        if not any(isinstance(value, TYPES[t]) and not (t == "integer" and isinstance(value, bool)) for t in types):
            return [f"{at}: {value!r} is not {types}"]
    if "enum" in schema and value not in schema["enum"]:
        out.append(f"{at}: {value!r} not in {schema['enum']}")
    if "const" in schema and value != schema["const"]:
        out.append(f"{at}: {value!r} is not {schema['const']!r}")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        out += [f"{at}: missing {k}" for k in schema.get("required", []) if k not in value]
        if schema.get("additionalProperties") is False:
            out += [f"{at}: unknown key {k}" for k in value if k not in props]
        for k, v in value.items():
            if k in props:
                out += problems(props[k], v, f"{at}.{k}")
    if isinstance(value, list) and "items" in schema:
        for i, v in enumerate(value):
            out += problems(schema["items"], v, f"{at}[{i}]")
    return out


class SearchSandbox(Sandbox):
    def setUp(self):
        super().setUp()
        patch = mock.patch.dict(os.environ, NO_LOG)
        patch.start()
        self.addCleanup(patch.stop)

    def page(self, name, summary, body, extra=""):
        """A wiki page outside wiki/systems/, so it needs no fixed sections."""
        (self.root / "wiki" / f"{name}.md").write_text(
            f'---\ntype: wiki\nsummary: "{summary}"\nowner: platform-team\n{extra}updated: 2026-10-01\n---\n{body}\n')

    def canary_pages(self):
        # aaa-notes sorts first by path and mentions the term once in the body
        self.page("aaa-notes", "Assorted notes", "We tried a canary once.")
        self.page("canary-releases", "Canary releases: how a canary reaches prod", "Start a canary at 5%.")

    def paths(self, *argv):
        _, out = run("--repo", str(self.root), "search", *argv)
        return [line.split("  ")[0] for line in out.splitlines()]


class RepoFilterTest(SearchSandbox):
    def test_in_repo_with_words_keeps_pages_without_repos(self):
        self.assertEqual(sorted(self.paths("gitops", "--in-repo", "platform")),
                         ["memory/findings/F-2026-09-16-001.md", "memory/incidents/I-2026-09-25-001.md",
                          "wiki/systems/gitops-server.md"])
        # the record of another repo is still left out
        self.assertNotIn("memory/findings/F-2026-09-20-001.md", self.paths("symlinks", "--in-repo", "platform"))

    def test_in_repo_without_words_lists_that_repos_records_only(self):
        self.assertEqual(self.paths("--in-repo", "platform"), ["memory/findings/F-2026-09-16-001.md"])

    def test_other_filters_still_drop_a_page(self):
        self.assertEqual(self.paths("gitops", "--in-repo", "platform", "--type", "finding"),
                         ["memory/findings/F-2026-09-16-001.md"])


class RankedSearchTest(SearchSandbox):
    @unittest.skipUnless(search.fts_available(), "this SQLite has no FTS5: the order falls back to terms held")
    def test_best_match_first_not_path_order(self):
        self.canary_pages()
        self.assertEqual(self.paths("canary"), ["wiki/canary-releases.md", "wiki/aaa-notes.md"])

    def test_partial_matches_follow_the_marker(self):
        self.canary_pages()
        full, partial = search.ranked(self.root, ["canary", "gitflow"])
        self.assertEqual(full, [])
        self.assertIn("wiki/canary-releases.md", [d["rel"] for d in partial])
        _, out = run("--repo", str(self.root), "search", "canary", "gitflow")
        self.assertEqual(out.splitlines()[0], search.PARTIAL)
        self.assertEqual(search.ranked(self.root, ["zzz", "qqq"]), ([], []))
        self.assertEqual(search.ranked(self.root, ["canary", "gitflow"], type="finding"), ([], []))

    def test_word_forms_reach_the_partial_group(self):
        self.canary_pages()
        _, partial = search.ranked(self.root, ["canaries"])  # no page holds the substring "canaries"
        if search.fts_available():
            self.assertEqual(partial[0]["rel"], "wiki/canary-releases.md")

    def test_without_fts5_the_same_records_come_back(self):
        self.canary_pages()
        want = search.ranked(self.root, ["canary", "gitflow"])
        with mock.patch.object(search, "scores", lambda docs, low: None):
            got = search.ranked(self.root, ["canary", "gitflow"])
            self.assertEqual({d["rel"] for d in got[1]}, {d["rel"] for d in want[1]})
            full, _ = search.ranked(self.root, ["canary", "start"])
            self.assertEqual([d["rel"] for d in full], ["wiki/canary-releases.md"])
            _, partial = search.ranked(self.root, ["canary", "start"])
            self.assertIn("wiki/aaa-notes.md", [d["rel"] for d in partial])

    def test_limit_counts_results_and_says_what_is_left(self):
        self.canary_pages()
        _, out = run("--repo", str(self.root), "search", "canary", "--limit", "1")
        self.assertEqual(len(out.splitlines()), 2)
        self.assertEqual(out.splitlines()[1], "(1 more with every term; --limit 0 shows all)")
        self.assertEqual(len(self.paths("canary", "--limit", "0")), 2)
        self.assertGreater(len(self.paths("gitops", "--limit", "0")), len(self.paths("gitops", "--limit", "1")))


class AliasTest(SearchSandbox):
    def test_a_page_is_found_by_its_alias_and_ranks_above_a_mention(self):
        self.page("aaa-notes", "Assorted notes", "We do not use gitflow.")
        self.page("release-flow", "How a change reaches prod", "Branches and tags.",
                  extra='aliases: [gitflow, "release strategy"]\n')
        self.assertIn("wiki/release-flow.md", self.paths("gitflow"))
        full, _ = search.ranked(self.root, ["release", "strategy"])
        self.assertEqual([d["rel"] for d in full], ["wiki/release-flow.md"])
        if search.fts_available():
            self.assertEqual(self.paths("gitflow")[0], "wiki/release-flow.md")

    def test_aliases_must_be_a_list(self):
        self.edit(self.root / "wiki" / "systems" / "gitops-server.md",
                  'aliases: [deploy server, "continuous delivery"]', "aliases: deploy server")
        errors, _ = records.check(self.root, today=dt.date(2026, 10, 1))
        self.assertTrue(any("aliases must be a list" in e for e in errors), errors)


class SearchJsonTest(SearchSandbox):
    def json(self, *argv):
        code, out = run("--repo", str(self.root), "search", *argv, "--json")
        self.assertEqual(code, 0)
        return json.loads(out)

    def test_output_follows_the_schema(self):
        for argv in (["token"], ["token", "rollout"], ["zzz"], ["--in-repo", "platform"],
                     ["gitops", "--limit", "1"], ["--type", "wiki"]):
            self.assertEqual(problems(SCHEMA, self.json(*argv)), [], argv)

    def test_fields_and_groups(self):
        doc = self.json("token", "rollout")
        self.assertEqual(doc["schema_version"], 1)
        self.assertEqual(doc["query"]["terms"], ["token", "rollout"])
        self.assertEqual(doc["total"], {"full": 1, "partial": 2})
        by_path = {r["path"]: r for r in doc["results"]}
        f = by_path["memory/findings/F-2026-09-16-001.md"]
        self.assertEqual((f["kind"], f["id"], f["status"], f["confidence"], f["match"]),
                         ("finding", "F-2026-09-16-001", "fixed", "verified", "partial"))
        self.assertEqual((f["repos"], f["systems"], f["expires"]), (["platform"], ["gitops-server"], "2027-03-15"))
        w = by_path["wiki/systems/gitops-server.md"]
        self.assertEqual((w["kind"], w["id"], w["status"], w["match"]), ("wiki", None, None, "full"))
        self.assertEqual(w["aliases"], ["deploy server", "continuous delivery"])

    def test_limit_and_totals(self):
        doc = self.json("gitops", "--limit", "1")
        self.assertEqual((len(doc["results"]), doc["total"]["full"]), (1, 3))
        self.assertEqual(self.json("zzz")["results"], [])
        self.assertEqual(len(self.json("--in-repo", "platform")["results"]), 1)  # no words: the whole list

    def test_the_checker_catches_a_drift(self):
        bad = {"schema_version": 1, "query": {}, "total": {"full": 0, "partial": 0}, "results": [{"path": 1}]}
        self.assertTrue(problems(SCHEMA, bad))


class QueryLogTest(Sandbox):
    def test_a_search_with_words_is_logged_and_a_listing_is_not(self):
        with mock.patch.dict(os.environ, {"ACME_KB_NO_QUERY_LOG": ""}):
            run("--repo", str(self.root), "search", "token", "gitflow", "--type", "finding")
            run("--repo", str(self.root), "search", "rollout", "--json")
            run("--repo", str(self.root), "search", "--in-repo", "platform")
        rows = querylog.read(self.root, days=0)
        self.assertEqual([r["terms"] for r in rows], [["token", "gitflow"], ["rollout"]])
        self.assertEqual((rows[0]["flags"], rows[0]["full"]), ({"type": "finding"}, 0))
        self.assertEqual(rows[1]["top"], ["memory/incidents/I-2026-09-25-001.md", "wiki/systems/gitops-server.md"])
        self.assertIn("/.queries/", (REPO / ".gitignore").read_text().splitlines())

    def test_switched_off_by_env_and_never_breaks_search(self):
        with mock.patch.dict(os.environ, NO_LOG):
            run("--repo", str(self.root), "search", "token")
        self.assertEqual(querylog.read(self.root, days=0), [])
        with mock.patch.dict(os.environ, {"ACME_KB_NO_QUERY_LOG": ""}):
            (self.root / ".queries").write_text("a file where the directory should be")
            code, out = run("--repo", str(self.root), "search", "zzz")
        self.assertEqual(code, 0)
        self.assertIn("no records match", out)

    def test_report_counts_misses_and_rephrasings(self):
        def log(terms, full, minutes, repo="platform"):
            querylog.record(self.root, terms, {}, full, 0, [], now=T0 + timedelta(minutes=minutes), repo=repo)
        log(["release", "strategy"], 0, 0)  # a miss, rephrased two minutes later
        log(["release", "flow"], 1, 2)
        log(["gitflow"], 0, 30)             # a miss, nobody rephrased
        log(["gitops", "token"], 3, 31, repo="agent-plugins")
        log(["gitflow"], 0, 90)
        rep = querylog.report(querylog.read(self.root, days=0))
        self.assertEqual((rep["searches"], rep["no_full"], rep["rephrased"]), (5, 3, 1))
        text = querylog.format_report(rep)
        self.assertIn("without a full match: 3 (60%)", text)
        self.assertIn("rephrased within 5 minutes: 1 (20%)", text)
        self.assertIn("2 x gitflow", text)
        _, out = run("--repo", str(self.root), "queries", "--days", "0")
        self.assertIn("searches: 5", out)

    def test_read_keeps_the_window_and_skips_broken_lines(self):
        querylog.record(self.root, ["old"], {}, 1, 0, [], now=T0 - timedelta(days=40))
        querylog.record(self.root, ["new"], {}, 1, 0, [], now=T0)
        with querylog.path(self.root, T0).open("a") as f:
            f.write("{not json\n")
        self.assertEqual([r["terms"] for r in querylog.read(self.root, days=30, now=T0)], [["new"]])
        self.assertEqual(len(querylog.read(self.root, days=0, now=T0)), 2)


class IndexTest(Sandbox):
    def test_map_has_one_line_per_system_with_open_counts(self):
        text = cli.build_index_map(self.root)
        self.assertIn("- gitops-server · [page](wiki/systems/gitops-server.md) · open 0 of 2 · The GitOps server", text)
        self.assertIn("- agent-tooling · no page · open 1 of 1", text)  # named by a record, no page yet
        self.assertIn("- payments · no page · open 0 of 1", text)
        self.assertNotIn("F-2026-09-16-001", text)  # records are counted, not listed

    def test_full_list_has_every_record(self):
        text = cli.build_index_full(self.root)
        for rec in records.load(self.root):
            self.assertIn(rec.meta.get("summary", ""), text)

    def test_both_files_stay_out_of_git(self):
        ignored = (REPO / ".gitignore").read_text().splitlines()
        self.assertIn("/index.md", ignored)
        self.assertIn("/index-full.md", ignored)


if __name__ == "__main__":
    unittest.main()
