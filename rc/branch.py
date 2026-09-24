"""World-repo branch contract. Packet PRs only."""

from __future__ import annotations

import re

from rc.delivery import is_receipt_path

PACKET_ID_RE = re.compile(r"^P-\d{8}-[a-z0-9]+$")
PACKET_BRANCH_RE = re.compile(r"^packet/P-\d{8}-[a-z0-9]+$")
ONBOARDING_BRANCH_RE = re.compile(r"^onboarding/[A-Za-z0-9._/-]+$")
RECEIPT_FILES = frozenset({"CERTIFICATE.json", "SUMMARY.md"})


def packet_branch(packet_id: str) -> str:
    return f"packet/{packet_id}"


def check_packet_id(packet_id: str) -> str | None:
    if not PACKET_ID_RE.match(packet_id or ""):
        return f"packet id must be P-YYYYMMDD-xxxx, got {packet_id!r}"
    return None


def check_world_branch(ref: str) -> str | None:
    """None if the ref may merge to a world main."""
    if PACKET_BRANCH_RE.match(ref or ""):
        return None
    if ONBOARDING_BRANCH_RE.match(ref or ""):
        return None
    return "branch must be packet/P-YYYYMMDD-xxxx or onboarding/..."


def allowed_lock_conflict(
    open_prs: list[dict], packet_id: str, allowed: list[str]
) -> str | None:
    """Refuse a second live PR that already touches this packet's work files."""
    work = set(allowed)
    want = packet_branch(packet_id)
    for pr in open_prs:
        head = ((pr.get("head") or {}).get("ref")) or ""
        if head == want:
            continue
        names = {n for n in (pr.get("files") or []) if not is_receipt_path(n)}
        hit = (names - RECEIPT_FILES) & work
        if hit:
            num = pr.get("number")
            return f"allowed_files lock pr=#{num} files={','.join(sorted(hit))}"
    return None
