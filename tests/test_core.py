"""Tests for Best-of-N Verifier Selector."""
import unittest
from best_of_n_verifier_selector.core import CandidatePatch, parse_diff_stats, select_best_patch


class TestBestOfNSelector(unittest.TestCase):
    def test_prefers_minimal_clean_passing_diff(self):
        small = CandidatePatch(
            "cand-small",
            "--- a/app.py\n+++ b/app.py\n@@ -1,2 +1,2 @@\n-x = 1\n+x = 2\n",
            tests_passed=True,
            tests_total=5,
            tests_passing_count=5,
        )
        bloated = CandidatePatch(
            "cand-bloated",
            "--- a/app.py\n+++ b/app.py\n@@ -1,2 +1,5 @@\n-x = 1\n+x = 2\n+y = 3\n+z = 4\n--- a/extra.py\n+++ b/extra.py\n@@ -1 +1 @@\n+pass\n",
            tests_passed=True,
            tests_total=5,
            tests_passing_count=5,
        )
        res = select_best_patch([bloated, small])
        self.assertIsNotNone(res.winner)
        self.assertEqual(res.winner.candidate_id, "cand-small")

    def test_protected_path_and_lint_errors_disqualify(self):
        bad = CandidatePatch(
            "cand-protected",
            "--- a/auth/rules.py\n+++ b/auth/rules.py\n@@ -1 +1 @@\n-deny()\n+allow()\n",
            tests_passed=True,
            lint_errors=1,
        )
        res = select_best_patch([bad], protected_paths=["auth/rules.py"])
        self.assertIsNone(res.winner)
        reasons = " ".join(res.leaderboard[0].rejection_reasons)
        self.assertIn("protected paths", reasons)
        self.assertIn("lint errors", reasons)

    def test_empty_diff_rejected_and_stats_parsed(self):
        stats = parse_diff_stats("--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-a\n+b\n+c\n")
        self.assertEqual(stats.files_touched, ["f.py"])
        self.assertEqual(stats.added_lines, 2)
        self.assertEqual(stats.removed_lines, 1)
        empty = CandidatePatch("empty", "", tests_passed=True)
        res = select_best_patch([empty])
        self.assertIsNone(res.winner)

    def test_empty_candidates_raises(self):
        with self.assertRaises(ValueError):
            select_best_patch([])
