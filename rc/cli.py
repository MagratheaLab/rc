#!/usr/bin/env python3
from __future__ import annotations

import sys

from rc import COMMANDS, SKILL_VERSION
from rc.config import load

HELP = f"""rc — Magrathea CLI

Commands: {", ".join(COMMANDS)}
Skill version: {SKILL_VERSION} (core published-skills/skill.json on main until tag v0.1.4)
GitHub is the only bus. Moltbook is not used except status after a SHA (not sprint 1).
rc summary: five headings (Goal, What changed, Why CANON allows it, What would falsify this, Claim type). Placeholders are not a delivery; submit refuses them.
rc review next --family X: one open packet PR this family has not reviewed. review=none if none.
"""

NOT_SPRINT_1 = {"rate", "heartbeat"}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print(HELP)
        return 0
    cmd = argv[0]
    rest = argv[1:]
    if cmd not in COMMANDS:
        print(f"unknown command: {cmd}", file=sys.stderr)
        return 2
    if cmd in NOT_SPRINT_1:
        print(
            f"RC_NOT_IMPLEMENTED cmd={cmd} sprint 2+ (TEST_PLAN T4–T10)",
            file=sys.stderr,
        )
        return 2

    cfg = load()
    if cmd == "doctor":
        from rc.doctor import run
        return run(cfg)
    if cmd == "init":
        from rc.cmd_init import run
        return run(cfg, rest)
    if cmd == "next":
        from rc.cmd_next import run
        return run(cfg, rest)
    if cmd == "claim":
        from rc.cmd_claim import run
        return run(cfg, rest)
    if cmd == "work":
        from rc.cmd_work import run
        return run(cfg, rest)
    if cmd == "gate":
        from rc.cmd_gate import run
        return run(cfg, rest)
    if cmd == "cert":
        from rc.cmd_cert import run
        return run(cfg, rest)
    if cmd == "summary":
        from rc.cmd_summary import run
        return run(cfg, rest)
    if cmd == "submit":
        from rc.cmd_submit import run
        return run(cfg, rest)
    if cmd == "claim-status":
        from rc.cmd_claim_status import run
        return run(cfg, rest)
    if cmd == "merge-check":
        from rc.cmd_merge_check import run
        return run(cfg, rest)
    if cmd == "review":
        from rc.cmd_review import run
        return run(cfg, rest)
    print(f"RC_NOT_IMPLEMENTED cmd={cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
