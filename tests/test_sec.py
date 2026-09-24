"""SEC catalog (unit path). Live PAT jobs stay blocked until owner grants user W."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rc.delivery import check_summary, check_tree, scan_secrets
from rc.packet import parse_packet_markdown
from tests.support import PACKET, fx01_cert, write_receipts
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
        changed = write_receipts(
            self.world,
            self.packet.packet,
            fx01_cert(gate={"local": "pass", "commands": []}),
            text,
        )
        errors = check_tree(
            self.world,
            self.packet,
            changed,
            require_delivery=True,
        )
        self.assertTrue(any("protocol_violation" in e for e in errors))

    def test_adv12_skill_version_mismatch_rejected(self):
        changed = write_receipts(
            self.world,
            self.packet.packet,
            fx01_cert(skill_version="0.1.0"),
            SUMMARY_OK,
        )
        errors = check_tree(
            self.world,
            self.packet,
            changed,
            require_delivery=True,
        )
        self.assertTrue(any("skill_version" in e for e in errors))

    def test_sec10_numeric_cannot_prove_rh(self):
        errors = check_summary("Goal\nThis proves RH.\n", claim_type="numeric")
        self.assertTrue(any("prove-language" in e or "millennium" in e for e in errors))

    def test_sec10_millennium_in_lemma_summary_rejected(self):
        errors = check_summary(
            SUMMARY_OK + "\nClay prize millennium solved.\n", claim_type="lemma"
        )
        self.assertTrue(any("millennium" in e for e in errors))
