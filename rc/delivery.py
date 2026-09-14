"""PR delivery checks (T2). Used by gate in CI and by submit."""

from __future__ import annotations

import json
import re
from pathlib import Path

from rc import DELIVERY_FILES, SKILL_VERSION
from rc.packet import Packet

SUMMARY_LIMIT = 500
SUMMARY_HEADINGS = (
    "Goal",
    "What changed",
    "Why CANON allows it",
    "What would falsify this",
    "Claim type",
)
PROVE_LANGUAGE = re.compile(
    r"\b(prove[sd]?|proof|qed|therefore\s+rh|rh\s+is\s+(true|proved))\b",
    re.I,
)
CERT_REQUIRED = (
    "packet",
    "claim_type",
    "skill_version",
    "canon_hash",
    "statement_hash",
    "agent_id",
    "family",
    "model_id",
    "allowed_files",
    "gate",
    "proof_kind",
    "summary",
)


def word_count(text: str) -> int:
    return len(text.split())


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check_summary(text: str, *, claim_type: str) -> list[str]:
    errors: list[str] = []
    words = word_count(text)
    if words > SUMMARY_LIMIT:
        errors.append(f"SUMMARY.md has {words} words (max {SUMMARY_LIMIT})")
    lower = text.lower()
    for heading in SUMMARY_HEADINGS:
        if heading.lower() not in lower:
            errors.append(f"SUMMARY.md missing heading: {heading}")
    if claim_type == "numeric" and PROVE_LANGUAGE.search(text):
        errors.append("numeric certificate cannot use prove-language in SUMMARY.md")
    return errors


def check_certificate(data: dict, packet: Packet) -> list[str]:
    errors: list[str] = []
    for key in CERT_REQUIRED:
        if key not in data:
            errors.append(f"CERTIFICATE.json missing {key}")
    if data.get("packet") != packet.packet:
        errors.append("CERTIFICATE.json packet id mismatch")
    if data.get("skill_version") != SKILL_VERSION:
        errors.append(
            f"CERTIFICATE.json skill_version {data.get('skill_version')!r} != {SKILL_VERSION}"
        )
    claim = data.get("claim_type")
    if claim and claim not in packet.extra.get("claim_types_allowed", [packet.claim_type]):
        # packet.claim_type is the assigned type; still allow blocked
        if claim not in {packet.claim_type, "blocked"}:
            errors.append(f"CERTIFICATE.json claim_type {claim} not allowed")
    return errors


def check_allowed_files(
    changed: list[str], packet: Packet, *, extra_ok: tuple[str, ...] = DELIVERY_FILES
) -> list[str]:
    allowed = set(packet.allowed_files)
    allowed.update(extra_ok)
    allowed.add(packet.path)
    errors = []
    for path in changed:
        if path.startswith(".rc/"):
            continue
        if path not in allowed:
            errors.append(f"diff touches file not in allowed_files: {path}")
    return errors


def check_tree(root: Path, packet: Packet, changed: list[str], *, require_delivery: bool) -> list[str]:
    errors: list[str] = []
    cert_path = root / "CERTIFICATE.json"
    summary_path = root / "SUMMARY.md"
    if require_delivery or cert_path.is_file() or summary_path.is_file():
        if not cert_path.is_file():
            errors.append("PR missing CERTIFICATE.json")
        if not summary_path.is_file():
            errors.append("PR missing SUMMARY.md")
    if cert_path.is_file():
        try:
            cert = load_json(cert_path)
        except json.JSONDecodeError as exc:
            return [f"CERTIFICATE.json invalid: {exc}"]
        errors.extend(check_certificate(cert, packet))
        claim = str(cert.get("claim_type") or packet.claim_type)
        if summary_path.is_file():
            errors.extend(
                check_summary(summary_path.read_text(encoding="utf-8"), claim_type=claim)
            )
    elif summary_path.is_file():
        errors.extend(
            check_summary(
                summary_path.read_text(encoding="utf-8"), claim_type=packet.claim_type
            )
        )
    errors.extend(check_allowed_files(changed, packet))
    return errors
