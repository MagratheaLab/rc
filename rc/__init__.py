__version__ = "0.1.4"
SKILL_VERSION = "0.1.4"
LEAN_PIN = "leanprover/lean4:v4.33.0"
COMMANDS = [
    "doctor",
    "init",
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
DELIVERY_FILES = ("CERTIFICATE.json", "SUMMARY.md")
CLAIM_TYPES = ("lemma", "numeric", "blocked", "adversary")
PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2}
