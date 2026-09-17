"""SEC catalog (unit path). Live PAT jobs stay blocked until owner grants user W."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rc.delivery import check_summary, check_tree, scan_secrets
from rc.packet import parse_packet_markdown
from tests.support import PACKET
from tests.test_t2_delivery import SUMMARY_OK


class TestSecUnit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.world = Path(self.tmp.name)
        self.packet = parse_packet_markdown(PACKET)

    def tearDown(self):
        self.tmp.cleanup()

    def test_sec4_secret_in_summary_rejected(self):
        text = SUMMARY_OK + "\ntoken ghp_" + ("a" * 36) + "\n"
        self.assertTrue(scan_secrets(text))
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
        self.assertTrue(any("protocol_violation" in e for e in errors))

    def test_sec10_numeric_cannot_prove_rh(self):
        errors = check_summary("Goal\nThis proves RH.\n", claim_type="numeric")
        self.assertTrue(any("prove-language" in e or "millennium" in e for e in errors))

    def test_sec10_millennium_in_lemma_summary_rejected(self):
        errors = check_summary(
            SUMMARY_OK + "\nClay prize millennium solved.\n", claim_type="lemma"
        )
        self.assertTrue(any("millennium" in e for e in errors))
