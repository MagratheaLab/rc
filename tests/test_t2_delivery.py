"""T2 Delivery — TEST_PLAN.md"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rc.branch import allowed_lock_conflict, check_packet_id, check_world_branch
from rc.cmd_submit import pr_body
from rc.delivery import check_tree, word_count
from rc.packet import parse_packet_markdown
from tests.support import (
    FakeCore,
    PACKET,
    SKILL,
    env_for,
    make_world,
    run_rc,
    serve,
)

SUMMARY_OK = """Goal
Build RiemannCanon.one_add_one.

What changed
Filled the fixture proof with rfl.

Why CANON allows it
Fixture island. claim_type lemma. Not RH.

What would falsify this
sorry, header rewrite, lake fail.

Claim type
lemma
"""


class TestT2Delivery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.world = make_world(self.root)
        self.packet = parse_packet_markdown(PACKET)
        self.core_url, self.core = serve(FakeCore, skill=dict(SKILL))
        self.addCleanup(self.core.shutdown)

    def tearDown(self):
        self.tmp.cleanup()

    def test_pr_without_certificate_rejected(self):
        (self.world / "SUMMARY.md").write_text(SUMMARY_OK, encoding="utf-8")
        errors = check_tree(self.world, self.packet, ["SUMMARY.md"], require_delivery=True)
        self.assertTrue(any("CERTIFICATE.json" in e for e in errors))

    def test_pr_without_summary_rejected(self):
        (self.world / "CERTIFICATE.json").write_text(
            json.dumps(
                {
                    "packet": "P-20260914-fx01",
                    "claim_type": "lemma",
                    "skill_version": "0.1.4",
                    "canon_hash": "sha256:" + "b" * 64,
                    "statement_hash": "sha256:" + "c" * 64,
                    "agent_id": "t",
                    "family": "A",
                    "model_id": "m",
                    "allowed_files": ["RiemannCanon.lean"],
                    "gate": {"local": "pass", "commands": ["lake build RiemannCanon"]},
                    "proof_kind": "lean",
                    "summary": "SUMMARY.md",
                }
            ),
            encoding="utf-8",
        )
        errors = check_tree(
            self.world, self.packet, ["CERTIFICATE.json"], require_delivery=True
        )
        self.assertTrue(any("SUMMARY.md" in e for e in errors))

    def test_summary_over_500_words_rejected(self):
        text = SUMMARY_OK + "\n" + " word" * 501
        self.assertGreater(word_count(text), 500)
        (self.world / "SUMMARY.md").write_text(text, encoding="utf-8")
        (self.world / "CERTIFICATE.json").write_text(
            json.dumps(
                {
                    "packet": "P-20260914-fx01",
                    "claim_type": "lemma",
                    "skill_version": "0.1.4",
                    "canon_hash": "sha256:" + "b" * 64,
                    "statement_hash": "sha256:" + "c" * 64,
                    "agent_id": "t",
                    "family": "A",
                    "model_id": "m",
                    "allowed_files": ["RiemannCanon.lean"],
                    "gate": {"local": "pass", "commands": []},
                    "proof_kind": "lean",
                    "summary": "SUMMARY.md",
                }
            ),
            encoding="utf-8",
        )
        errors = check_tree(
            self.world,
            self.packet,
            ["CERTIFICATE.json", "SUMMARY.md"],
            require_delivery=True,
        )
        self.assertTrue(any("500" in e for e in errors))

    def test_numeric_prove_language_rejected(self):
        from rc.delivery import check_summary

        errors = check_summary("Goal\nThis proves RH.\n", claim_type="numeric")
        self.assertTrue(any("prove-language" in e for e in errors))

    def test_diff_outside_allowed_files_rejected(self):
        errors = check_tree(
            self.world, self.packet, ["SECRET.md"], require_delivery=False
        )
        self.assertTrue(any("SECRET.md" in e for e in errors))

    def test_submit_pr_body_closes_packet_issue(self):
        self.assertIn("Closes #12", pr_body("P-20260914-fx01", "lemma", 12))
        self.assertNotIn("Closes", pr_body("P-20260914-fx01", "lemma", None))

    def test_packet_branch_contract(self):
        self.assertIsNone(check_packet_id("P-20260914-fx01"))
        self.assertIsNotNone(check_packet_id("fx01"))
        self.assertIsNone(check_world_branch("packet/P-20260914-fx01"))
        self.assertIsNone(check_world_branch("onboarding/p1-branch"))
        self.assertIsNotNone(check_world_branch("feature/oops"))
        other = {
            "number": 3,
            "head": {"ref": "packet/P-20260914-num01"},
            "files": ["numeric/fx_interval.py", "CERTIFICATE.json"],
        }
        self.assertIsNone(
            allowed_lock_conflict(
                [other], "P-20260914-fx01", ["RiemannCanon.lean"]
            )
        )
        self.assertIn(
            "lock",
            allowed_lock_conflict(
                [other], "P-20260914-num01-b", ["numeric/fx_interval.py"]
            )
            or "",
        )

    def test_submit_refuses_without_certificate(self):
        env = env_for(self.world, "http://127.0.0.1:9", self.core_url)
        run_rc(["work", "P-20260914-fx01"], env, self.world)
        code, _out, err = run_rc(
            ["submit", "P-20260914-fx01", "--dry-run"], env, self.world
        )
        self.assertEqual(code, 1)
        self.assertIn("CERTIFICATE.json", err)
