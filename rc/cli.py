#!/usr/bin/env python3
import sys

SKILL = "0.1.4"
COMMANDS = [
    "doctor",
    "next",
    "claim",
    "work",
    "gate",
    "cert",
    "summary",
    "submit",
    "review",
    "rate",
    "merge-check",
    "heartbeat",
    "claim-status",
]

HELP = """rc — Magrathea CLI stub

Commands: {cmds}
Skill version expected: {skill}
Most commands exit 2 until Grok Build implements them.
""".format(cmds=", ".join(COMMANDS), skill=SKILL)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print(HELP)
        return 0
    cmd = argv[0]
    if cmd == "doctor":
        print(f"RC_STUB skill_expected={SKILL}")
        print("RC_STUB fetch MagratheaLab/core published-skills/skill.json on main until tag v0.1.4")
        print("RC_STUB lean pin leanprover/lean4:v4.33.0 (see ops/DECISIONS.md)")
        print("RC_STUB fixture packet P-20260914-fx01 on MagratheaLab/riemann")
        print("RC_STUB not implemented: GitHub auth, sparse checkout, lake gate")
        return 0
    if cmd not in COMMANDS:
        print(f"unknown command: {cmd}", file=sys.stderr)
        return 2
    print(f"RC_NOT_IMPLEMENTED cmd={cmd} implement in Grok Build (TEST_PLAN T0-T10)")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
