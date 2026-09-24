"""T2 Delivery — TEST_PLAN.md"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rc.branch import allowed_lock_conflict, check_packet_id, check_world_branch
from rc.cmd_submit import pr_body
from rc.delivery import check_summary, check_tree, word_count
from rc.packet import parse_packet_markdown
from tests.support import (
    FakeCore,
    PACKET,
    SKILL,
    env_for,
    fx01_cert,
    make_world,
    run_rc,
    serve,
    write_receipts,
)

FORD_TEMPLATE = """Goal
T8 join fixture — second GitHub user claims, gates, and submits a certificate for t8w/T8Join.lean.

What changed
(describe the smallest diff)

Why CANON allows it
(identifier + hash)

What would falsify this
(header rewrite, sorry, lake fail)

Claim type
lemma

Fixture packet. Not RH. SUMMARY is an account, not a proof.
"""

SUMMARY_OK = """Goal
P-20260914-fx01 Build RiemannCanon.one_add_one.

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
        write_receipts(self.world, self.packet.packet, fx01_cert(), SUMMARY_OK)
        (self.world / "receipts" / self.packet.packet / "CERTIFICATE.json").unlink()
        errors = check_tree(
            self.world,
            self.packet,
            ["receipts/P-20260914-fx01/SUMMARY.md"],
            require_delivery=True,
        )
        self.assertTrue(any("CERTIFICATE.json" in e for e in errors))

    def test_pr_without_summary_rejected(self):
        write_receipts(self.world, self.packet.packet, fx01_cert(), SUMMARY_OK)
        (self.world / "receipts" / self.packet.packet / "SUMMARY.md").unlink()
        errors = check_tree(
            self.world,
            self.packet,
            ["receipts/P-20260914-fx01/CERTIFICATE.json"],
            require_delivery=True,
        )
        self.assertTrue(any("SUMMARY.md" in e for e in errors))

    def test_summary_over_500_words_rejected(self):
        text = SUMMARY_OK + "\n" + " word" * 501
        self.assertGreater(word_count(text), 500)
        changed = write_receipts(
            self.world, self.packet.packet, fx01_cert(gate={"local": "pass", "commands": []}), text
        )
        errors = check_tree(
            self.world,
            self.packet,
            changed,
            require_delivery=True,
        )
        self.assertTrue(any("500" in e for e in errors))

    def test_receipts_dir_is_not_an_allowed_files_violation(self):
        changed = write_receipts(self.world, self.packet.packet, fx01_cert(), SUMMARY_OK)
        errors = check_tree(
            self.world, self.packet, changed + ["RiemannCanon.lean"], require_delivery=True
        )
        self.assertFalse(any("allowed_files" in e for e in errors))

    def test_root_leftover_receipt_still_accepted(self):
        (self.world / "SUMMARY.md").write_text(SUMMARY_OK, encoding="utf-8")
        (self.world / "CERTIFICATE.json").write_text(
            json.dumps(fx01_cert(summary="SUMMARY.md")), encoding="utf-8"
        )
        errors = check_tree(
            self.world,
            self.packet,
            ["CERTIFICATE.json", "SUMMARY.md"],
            require_delivery=True,
        )
        self.assertFalse(any("PR missing" in e for e in errors))

    def test_numeric_prove_language_rejected(self):
        errors = check_summary("Goal\nThis proves RH.\n", claim_type="numeric")
        self.assertTrue(any("prove-language" in e for e in errors))

    def test_summary_rejects_placeholders(self):
        errors = check_summary(
            FORD_TEMPLATE, claim_type="lemma", packet_id="P-20260924-t8w"
        )
        self.assertTrue(any("SUMMARY_TEMPLATE" in e for e in errors))

    def test_summary_rejects_empty_section(self):
        text = """Goal
P-20260914-fx01 x.

What changed

Why CANON allows it
fixture.

What would falsify this
sorry.

Claim type
lemma
"""
        errors = check_summary(text, claim_type="lemma", packet_id="P-20260914-fx01")
        self.assertTrue(any("SUMMARY_EMPTY:What changed" in e for e in errors))

    def test_summary_claim_type_first_token_only(self):
        text = SUMMARY_OK.replace("Claim type\nlemma", "Claim type\nlemma — a local fixture, not RH.")
        errors = check_summary(text, claim_type="lemma", packet_id="P-20260914-fx01")
        self.assertEqual(errors, [])

    def test_summary_accepts_minimal_real_five_sections(self):
        errors = check_summary(
            SUMMARY_OK, claim_type="lemma", packet_id="P-20260914-fx01"
        )
        self.assertEqual(errors, [])

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
            "files": ["numeric/fx_interval.py", "receipts/P-20260914-num01/CERTIFICATE.json"],
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

    def test_submit_refuses_template_summary(self):
        changed = write_receipts(
            self.world, self.packet.packet, fx01_cert(), FORD_TEMPLATE
        )
        errors = check_tree(
            self.world, self.packet, changed, require_delivery=True
        )
        self.assertTrue(any("SUMMARY_TEMPLATE" in e for e in errors))

    def test_submit_refuses_without_certificate(self):
        env = env_for(self.world, "http://127.0.0.1:9", self.core_url)
        run_rc(["work", "P-20260914-fx01"], env, self.world)
        code, _out, err = run_rc(
            ["submit", "P-20260914-fx01", "--dry-run"], env, self.world
        )
        self.assertEqual(code, 1)
        self.assertIn("CERTIFICATE.json", err)
