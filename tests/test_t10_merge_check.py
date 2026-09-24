"""T10 Merge check — TEST_PLAN.md. Never merges."""

from __future__ import annotations

import json
import unittest

from rc.cmd_merge_check import evaluate, render


def _pr():
    return {
        "number": 7,
        "head": {"sha": "abc123def4567890", "ref": "packet/P-20260914-fx01"},
    }


CERT_REL = "receipts/P-20260914-fx01/CERTIFICATE.json"
SUM_REL = "receipts/P-20260914-fx01/SUMMARY.md"


def _ok_files():
    return [
        {"filename": "RiemannCanon.lean", "patch": "+theorem one_add_one : 1 + 1 = 2 := rfl\n"},
        {"filename": CERT_REL, "patch": ""},
        {"filename": SUM_REL, "patch": ""},
    ]


def _ok_contents():
    return {
        "RiemannCanon.lean": "theorem one_add_one : 1 + 1 = 2 := rfl\n",
        CERT_REL: json.dumps(
            {
                "packet": "P-20260914-fx01",
                "claim_type": "lemma",
                "statement_hash": "sha256:" + "a" * 64,
                "allowed_files": ["RiemannCanon.lean"],
            }
        ),
        SUM_REL: "Goal\nP-20260914-fx01 fixture one_add_one.\n\nWhat changed\nrfl\n\nWhy CANON allows it\nfixture\n\nWhat would falsify this\nsorry\n\nClaim type\nlemma\n",
    }


def _reviews(adv=True):
    bodies = [
        "MAGRATHEA_REVIEW\nfamily: A\nadversary: false\nverdict: accept\npacket: P-20260914-fx01\n",
        "MAGRATHEA_REVIEW\nfamily: B\nadversary: false\nverdict: accept\npacket: P-20260914-fx01\n",
    ]
    if adv:
        bodies.append(
            "MAGRATHEA_REVIEW\nfamily: C\nadversary: true\nverdict: accept\npacket: P-20260914-fx01\n"
        )
    return [{"body": b} for b in bodies]


def _gate_ok():
    return [{"name": "gate", "conclusion": "success"}]


class TestT10MergeCheck(unittest.TestCase):
    def test_complete_fixture_is_go(self):
        card = evaluate(
            pr=_pr(),
            files=_ok_files(),
            check_runs=_gate_ok(),
            comments=_reviews(True),
            file_contents=_ok_contents(),
        )
        self.assertEqual(card["VERDICT"], "GO")
        self.assertEqual(card["GATE"], "PASS")
        self.assertEqual(card["ADVERSARY"], "PASS")
        self.assertEqual(card["BRANCH"], "PASS")
        self.assertEqual(card["SORRY_OR_REWRITE"], "CLEAN")
        text = render(card)
        self.assertIn("MERGE_CHECK pr=7", text)
        self.assertIn("VERDICT              GO", text)

    def test_public_pr_comment_without_packet_is_not_quorum(self):
        leaked = [
            {"body": "LGTM family A accept\n"},
            {
                "body": "MAGRATHEA_REVIEW\nfamily: A\nadversary: true\nverdict: accept\n"
            },
            {
                "body": "MAGRATHEA_REVIEW\nfamily: B\nadversary: false\nverdict: accept\n"
            },
            {
                "body": "MAGRATHEA_REVIEW\nfamily: C\nadversary: false\nverdict: accept\n"
            },
        ]
        card = evaluate(
            pr=_pr(),
            files=_ok_files(),
            check_runs=_gate_ok(),
            comments=leaked,
            file_contents=_ok_contents(),
        )
        self.assertEqual(card["VERDICT"], "NO-GO")
        self.assertIn("FAMILIES", card["BLOCKERS"])

    def test_missing_adversary_is_nogo(self):
        card = evaluate(
            pr=_pr(),
            files=_ok_files(),
            check_runs=_gate_ok(),
            comments=_reviews(False),
            file_contents=_ok_contents(),
        )
        self.assertEqual(card["VERDICT"], "NO-GO")
        self.assertIn("ADVERSARY", card["BLOCKERS"])
        self.assertEqual(card["ADVERSARY"], "MISSING")

    def test_missing_summary_is_nogo(self):
        contents = _ok_contents()
        del contents[SUM_REL]
        files = [f for f in _ok_files() if f["filename"] != SUM_REL]
        card = evaluate(
            pr=_pr(),
            files=files,
            check_runs=_gate_ok(),
            comments=_reviews(True),
            file_contents=contents,
        )
        self.assertEqual(card["VERDICT"], "NO-GO")
        self.assertIn("SUMMARY_MISSING", card["BLOCKERS"])

    def test_merge_check_nogo_on_template_summary(self):
        from tests.test_t2_delivery import FORD_TEMPLATE

        contents = _ok_contents()
        contents[SUM_REL] = FORD_TEMPLATE
        card = evaluate(
            pr=_pr(),
            files=_ok_files(),
            check_runs=_gate_ok(),
            comments=_reviews(True),
            file_contents=contents,
        )
        self.assertEqual(card["VERDICT"], "NO-GO")
        self.assertIn("SUMMARY_TEMPLATE", card["BLOCKERS"])

    def test_non_packet_branch_is_nogo(self):
        pr = _pr()
        pr["head"]["ref"] = "feature/oops"
        card = evaluate(
            pr=pr,
            files=_ok_files(),
            check_runs=_gate_ok(),
            comments=_reviews(True),
            file_contents=_ok_contents(),
        )
        self.assertEqual(card["VERDICT"], "NO-GO")
        self.assertEqual(card["BRANCH"], "FAIL")
        self.assertIn("BRANCH", card["BLOCKERS"])

    def test_sorry_in_diff_is_nogo(self):
        contents = _ok_contents()
        contents["RiemannCanon.lean"] = "theorem one_add_one : 1 + 1 = 2 := sorry\n"
        files = [
            {"filename": "RiemannCanon.lean", "patch": "+theorem one_add_one : 1 + 1 = 2 := sorry\n"},
            {"filename": CERT_REL, "patch": ""},
            {"filename": SUM_REL, "patch": ""},
        ]
        card = evaluate(
            pr=_pr(),
            files=files,
            check_runs=_gate_ok(),
            comments=_reviews(True),
            file_contents=contents,
        )
        self.assertEqual(card["VERDICT"], "NO-GO")
        self.assertEqual(card["SORRY_OR_REWRITE"], "HIT")

    def test_cli_never_posts_merge(self):
        from tests.support import FakeCore, FakeGitHub, SKILL, env_for, make_world, run_rc, serve
        import tempfile
        from pathlib import Path

        tmp = tempfile.TemporaryDirectory()
        world = make_world(Path(tmp.name))
        store = {
            "issues": [],
            "comments": {},
            "login": "tester",
            "urls": [],
            "pulls": {
                7: {
                    "number": 7,
                    "head": {"sha": "abc123def456"},
                }
            },
            "pr_files": {7: _ok_files()},
            "check_runs": _gate_ok(),
            "comments": {7: _reviews(True)},
        }
        gh_url, httpd = serve(FakeGitHub, store=store)
        core_url, core = serve(FakeCore, skill=dict(SKILL))
        try:
            env = env_for(world, gh_url, core_url)
            run_rc(["merge-check", "MagratheaLab/riemann", "7"], env, world)
            urls = " ".join(store.get("urls") or [])
            self.assertNotIn("/merge", urls)
            self.assertNotIn("PUT", urls)
        finally:
            httpd.shutdown()
            core.shutdown()
            tmp.cleanup()
