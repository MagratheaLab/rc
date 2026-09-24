"""T1 Packet lifecycle — TEST_PLAN.md"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tests.support import (
    FakeCore,
    FakeGitHub,
    SKILL,
    env_for,
    issue,
    make_world,
    run_rc,
    serve,
)


def _until(hours: float) -> str:
    t = datetime.now(timezone.utc) + timedelta(hours=hours)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


class TestT1Lifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.world = make_world(self.root)
        self.core_url, self.core = serve(FakeCore, skill=dict(SKILL))

    def tearDown(self):
        self.core.shutdown()
        self.tmp.cleanup()

    def _gh(self, iss):
        store = {"issues": [iss], "comments": {}, "login": "tester"}
        url, httpd = serve(FakeGitHub, store=store)
        self.addCleanup(httpd.shutdown)
        return url, store

    def test_open_packet_is_issue_with_label_packet(self):
        url, store = self._gh(issue())
        env = env_for(self.world, url, self.core_url)
        code, out, err = run_rc(["next"], env, self.world)
        self.assertEqual(code, 0, err)
        self.assertIn("labels=packet", out)

    def test_claim_sets_assignee_and_claimed_label(self):
        url, store = self._gh(issue())
        env = env_for(self.world, url, self.core_url)
        code, out, err = run_rc(["claim", "P-20260914-fx01"], env, self.world)
        self.assertEqual(code, 0, err)
        iss = store["issues"][0]
        names = {l["name"] for l in iss["labels"]}
        self.assertIn("claimed", names)
        self.assertIn("packet", names)
        self.assertEqual(iss["assignees"][0]["login"], "tester")
        self.assertIn("claimed_until:", iss["body"])
        self.assertIn("label=claimed", out)
        self.assertIn("lemma", names)
        self.assertIn("P2", names)

    def test_next_ignores_question_issues(self):
        from rc.cmd_next import select_issue

        q = issue(
            title="Q: why this lemma",
            body="not a packet",
            labels=[{"name": "question"}],
        )
        mixed = issue(
            number=2,
            title="P-20260914-fx01 but also question",
            labels=[{"name": "packet"}, {"name": "question"}],
        )
        packet = issue(number=3, title="P-20260914-fx01 fixture Lean island")
        self.assertIsNone(select_issue([q], {}, ""))
        self.assertIsNone(select_issue([mixed], {}, ""))
        chosen = select_issue([q, mixed, packet], {}, "")
        self.assertEqual(chosen["number"], 3)

    def test_next_skips_packet_plus_question_via_api(self):
        mixed = issue(
            title="P-20260914-fx01 but also question",
            labels=[{"name": "packet"}, {"name": "question"}],
        )
        url, _store = self._gh(mixed)
        env = env_for(self.world, url, self.core_url)
        code, out, err = run_rc(["next"], env, self.world)
        self.assertEqual(code, 0, err)
        self.assertIn("packet=none", out)
        self.assertIn("IDLE", out)

    def test_claim_refuses_packet_plus_question(self):
        mixed = issue(
            labels=[{"name": "packet"}, {"name": "question"}],
        )
        url, _store = self._gh(mixed)
        env = env_for(self.world, url, self.core_url)
        code, _out, err = run_rc(["claim", "P-20260914-fx01"], env, self.world)
        self.assertEqual(code, 1)
        self.assertIn("CLAIM_FAIL", err)
        self.assertIn("question", err)

    def test_observer_at_mention_is_not_work(self):
        q = issue(
            title="Q: please do fx01",
            body="not a packet",
            labels=[{"name": "question"}],
        )
        url, store = self._gh(q)
        store["comments"] = {
            1: [{"body": "@tester doe packet P-20260914-fx01"}]
        }
        env = env_for(self.world, url, self.core_url)
        env["RC_AGENT_ID"] = "tester"
        code, out, err = run_rc(["next"], env, self.world)
        self.assertEqual(code, 0, err)
        self.assertIn("packet=none", out)
        self.assertIn("IDLE", out)

    def test_worker_named_hermes_does_not_post_assign(self):
        url, store = self._gh(issue())
        env = env_for(self.world, url, self.core_url)
        env["RC_AGENT_ID"] = "Hermes"
        code, _out, err = run_rc(["next"], env, self.world)
        self.assertEqual(code, 0, err)
        code, _out, err = run_rc(["claim", "P-20260914-fx01"], env, self.world)
        self.assertEqual(code, 0, err)
        blob = " ".join(store.get("urls") or [])
        comments = store.get("comments") or {}
        bodies = " ".join(
            c.get("body") or "" for cs in comments.values() for c in cs
        )
        self.assertNotIn("DISPATCH_ASSIGN", blob)
        self.assertNotIn("HERMES_ASSIGN", blob)
        self.assertNotIn("DISPATCH_ASSIGN", bodies)
        self.assertNotIn("HERMES_ASSIGN", bodies)

    def test_second_claim_fails(self):
        body = (
            "packet: P-20260914-fx01\npriority: P2\nclaim_type: lemma\nttl: 24h\n"
            f"claimed_until: {_until(24)}\n"
        )
        iss = issue(
            body=body,
            labels=[{"name": "packet"}, {"name": "claimed"}],
            assignees=[{"login": "other"}],
            assignee={"login": "other"},
        )
        url, _store = self._gh(iss)
        env = env_for(self.world, url, self.core_url)
        code, _out, err = run_rc(["claim", "P-20260914-fx01"], env, self.world)
        self.assertEqual(code, 1)
        self.assertIn("CLAIM_FAIL", err)

    def test_expired_ttl_releases_lock(self):
        body = (
            "packet: P-20260914-fx01\npriority: P2\nclaim_type: lemma\nttl: 24h\n"
            f"claimed_until: {_until(-1)}\n"
        )
        iss = issue(
            body=body,
            labels=[{"name": "packet"}, {"name": "claimed"}],
            assignees=[{"login": "other"}],
            assignee={"login": "other"},
        )
        url, store = self._gh(iss)
        env = env_for(self.world, url, self.core_url)
        code, out, err = run_rc(["claim", "P-20260914-fx01"], env, self.world)
        self.assertEqual(code, 0, err)
        self.assertEqual(store["issues"][0]["assignees"][0]["login"], "tester")
        self.assertIn("claimed", {l["name"] for l in store["issues"][0]["labels"]})

    def test_work_checkout_only_allowed_files_and_packet(self):
        env = env_for(self.world, "http://127.0.0.1:9", self.core_url)
        code, out, err = run_rc(["work", "P-20260914-fx01"], env, self.world)
        self.assertEqual(code, 0, err)
        work = self.world / ".rc" / "work" / "P-20260914-fx01"
        present = sorted(
            p.relative_to(work).as_posix() for p in work.rglob("*") if p.is_file()
        )
        self.assertEqual(present, ["RiemannCanon.lean", "packets/P-20260914-fx01.md"])
        self.assertFalse((work / "SECRET.md").exists())
        self.assertFalse((work / "lakefile.toml").exists())
        self.assertFalse((work / "defs" / "CANON.md").exists())
        self.assertIn("files=RiemannCanon.lean,packets/P-20260914-fx01.md", out)
