from __future__ import annotations

import sys
from pathlib import Path

from rc.config import Config
from rc.delivery import SUMMARY_HEADINGS, check_summary, receipt_files, word_count
from rc.packet import load_packet_file
from rc.state import find_world, work_dir

TEMPLATE = """Goal
{goal}

What changed
(describe the smallest diff)

Why CANON allows it
(identifier + hash)

What would falsify this
(header rewrite, sorry, lake fail)

Claim type
{claim_type}

Fixture packet. Not RH. SUMMARY is an account, not a proof.
"""


def run(cfg: Config, argv: list[str]) -> int:
    packet_id = next((a for a in argv if a.startswith("P-")), "")
    world = find_world(cfg.world)
    if not packet_id:
        print("usage: rc summary P-...", file=sys.stderr)
        return 2
    packet = load_packet_file(world, packet_id)
    work = work_dir(world, packet_id)
    root = work if work.is_dir() else world
    _cert_rel, sum_rel = receipt_files(packet.packet)
    path = root / sum_rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        path.write_text(
            TEMPLATE.format(goal=packet.goal or packet.packet, claim_type=packet.claim_type),
            encoding="utf-8",
        )
        print(f"wrote_template={path}")
    text = path.read_text(encoding="utf-8")
    errors = check_summary(text, claim_type=packet.claim_type)
    print(f"words={word_count(text)}")
    print(f"path={path}")
    if errors:
        for err in errors:
            print(f"SUMMARY_FAIL {err}", file=sys.stderr)
        return 1
    print("SUMMARY_OK")
    return 0
