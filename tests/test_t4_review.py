"""T4 Blind review store — private until quorum, then batch-publish."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.support import (
    FakeCore,
    FakeGitHub,
    SKILL,
    env_for,
    make_world,
    run_rc,
    serve,
)


class TestT4Review(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.world = make_world(Path(self.tmp.name))
        self.store = {"issues": [], "comments": {}, "login": "tester", "urls": []}
        self.gh_url, self.gh = serve(FakeGitHub, store=self.store)
        self.core_url, self.core = serve(FakeCore, skill=dict(SKILL))
        self.env = env_for(self.world, self.gh_url, self.core_url)
        self.env["RC_REVIEW_REPO"] = "MagratheaLab/reviews"

    def tearDown(self):
        self.gh.shutdown()
        self.core.shutdown()
        self.tmp.cleanup()

    def _submit(self, family, *, adv=False):
        args = [
            "review",
            "submit",
            "P-20260914-fx01",
            "--pr",
            "9",
            "--family",
            family,
            "--verdict",
            "accept",
        ]
        if adv:
            args.append("--adversary")
        return run_rc(args, self.env, self.world)

    def test_review_next_skips_family_already_submitted(self):
        self.store["open_prs"] = [
            {
                "number": 9,
                "title": "P-20260914-fx01",
                "body": "packet",
                "head": {"ref": "packet/P-20260914-fx01"},
            },
            {
                "number": 10,
                "title": "docs",
                "body": "onboarding",
                "head": {"ref": "onboarding/docs"},
            },
        ]
        code, out, err = run_rc(
            ["review", "next", "--family", "A"], self.env, self.world
        )
        self.assertEqual(code, 0, err)
        self.assertIn("packet=P-20260914-fx01", out)
        self.assertIn("pr=9", out)
        self._submit("A")
        code, out, err = run_rc(
            ["review", "next", "--family", "A"], self.env, self.world
        )
        self.assertEqual(code, 0, err)
        self.assertIn("review=none", out)
        code, out, err = run_rc(
            ["review", "next", "--family", "B"], self.env, self.world
        )
        self.assertEqual(code, 0, err)
        self.assertIn("packet=P-20260914-fx01", out)

    def test_one_verdict_stays_pending_not_on_world_pr(self):
        code, out, err = self._submit("A")
        self.assertEqual(code, 0, err)
        self.assertIn("pending=yes", out)
        self.assertIn("quorum=no", out)
        self.assertEqual(self.store.get("comments", {}).get(9, []), [])
        self.assertEqual(len(self.store["issues"]), 1)

    def test_quorum_publishes_batch_to_world_pr(self):
        self._submit("A")
        self._submit("B")
        code, out, err = self._submit("C", adv=True)
        self.assertEqual(code, 0, err)
        self.assertIn("quorum=yes", out)
        comments = self.store.get("comments", {}).get(9, [])
        self.assertEqual(len(comments), 3)
        bodies = " ".join(c["body"] for c in comments)
        self.assertIn("family: A", bodies)
        self.assertIn("family: C", bodies)
        self.assertIn("adversary: true", bodies)
        urls = " ".join(self.store.get("urls") or [])
        self.assertNotIn("/merge", urls)
