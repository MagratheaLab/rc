"""PR delivery checks (T2). Used by gate in CI and by submit."""

from __future__ import annotations

import json
import re
from pathlib import Path

from rc import SKILL_VERSION
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
MILLENNIUM = re.compile(
    r"\b(millennium|clay prize|proves RH|RH is (true|proved))\b",
    re.I,
)
SECRET_MARKERS = re.compile(
    r"ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----",
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


def receipt_dir(packet_id: str) -> str:
    return f"receipts/{packet_id}"


def receipt_files(packet_id: str) -> tuple[str, str]:
    d = receipt_dir(packet_id)
    return f"{d}/CERTIFICATE.json", f"{d}/SUMMARY.md"


def is_receipt_path(path: str) -> bool:
    return (path or "").startswith("receipts/")


def resolve_receipt_paths(root: Path, packet_id: str) -> tuple[Path, Path]:
    """Prefer receipts/<id>/; fall back to repo-root leftovers."""
    cert_rel, sum_rel = receipt_files(packet_id)
    cert = root / cert_rel
    summary = root / sum_rel
    if cert.is_file() or summary.is_file():
        return cert, summary
    return root / "CERTIFICATE.json", root / "SUMMARY.md"


def pick_receipt_text(file_contents: dict[str, str], basename: str) -> str | None:
    """PR head: receipts/<id>/<basename> wins over a root leftover."""
    matches = [
        file_contents[k]
        for k in file_contents
        if k.endswith("/" + basename) and is_receipt_path(k)
    ]
    if matches:
        return matches[0]
    return file_contents.get(basename)


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
    if MILLENNIUM.search(text):
        errors.append("never claim a millennium problem in SUMMARY.md")
    return errors


def scan_secrets(text: str) -> list[str]:
    if SECRET_MARKERS.search(text or ""):
        return ["protocol_violation: secret material in delivery"]
    return []


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
    changed: list[str], packet: Packet, *, extra_ok: tuple[str, ...] | None = None
) -> list[str]:
    cert_rel, sum_rel = receipt_files(packet.packet)
    extra = extra_ok if extra_ok is not None else (cert_rel, sum_rel, "CERTIFICATE.json", "SUMMARY.md")
    allowed = set(packet.allowed_files)
    allowed.update(extra)
    allowed.add(packet.path)
    errors = []
    for path in changed:
        if path.startswith(".rc/") or is_receipt_path(path):
            continue
        if path not in allowed:
            errors.append(f"diff touches file not in allowed_files: {path}")
    return errors


def check_tree(root: Path, packet: Packet, changed: list[str], *, require_delivery: bool) -> list[str]:
    errors: list[str] = []
    cert_path, summary_path = resolve_receipt_paths(root, packet.packet)
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
    blob_parts: list[str] = []
    for path in (cert_path, summary_path):
        if path.is_file():
            blob_parts.append(path.read_text(encoding="utf-8", errors="replace"))
    for rel in changed:
        path = root / rel
        if path.is_file() and path.suffix.lower() in {".md", ".json", ".lean", ".txt", ".yml", ".yaml"}:
            blob_parts.append(path.read_text(encoding="utf-8", errors="replace"))
    errors.extend(scan_secrets("\n".join(blob_parts)))
    return errors
