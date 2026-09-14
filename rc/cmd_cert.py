from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from rc import SKILL_VERSION
from rc.config import Config
from rc.linter import sha256_text, statement_hash
from rc.packet import load_packet_file
from rc.state import find_world, load_state, work_dir


def _file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def run(cfg: Config, argv: list[str]) -> int:
    packet_id = next((a for a in argv if a.startswith("P-")), "")
    world = find_world(cfg.world)
    if not packet_id:
        print("usage: rc cert P-...", file=sys.stderr)
        return 2
    packet = load_packet_file(world, packet_id)
    work = work_dir(world, packet_id)
    root = work if work.is_dir() else world
    stamp_path = world / ".rc" / f"gate-{packet.packet}.json"
    if not stamp_path.is_file():
        print("run rc gate before rc cert", file=sys.stderr)
        return 1
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    if not stamp.get("pass"):
        print("gate did not pass; cert not written", file=sys.stderr)
        return 1

    canon = world / "defs" / "CANON.md"
    canon_hash = _file_hash(canon) if canon.is_file() else "sha256:" + "0" * 64
    lean_path = None
    for rel in packet.allowed_files:
        candidate = root / rel
        if candidate.suffix == ".lean" and candidate.is_file():
            lean_path = candidate
            break
    src = lean_path.read_text(encoding="utf-8") if lean_path else ""
    stmt = (
        statement_hash(src, packet.lean_declaration)
        if packet.lean_declaration
        else sha256_text(src)
    )
    proof_kind = {
        "lemma": "lean",
        "numeric": "numeric_interval",
        "blocked": "blocked",
        "adversary": "hole",
    }.get(packet.claim_type, "lean")
    cert = {
        "packet": packet.packet,
        "claim_type": packet.claim_type,
        "skill_version": SKILL_VERSION,
        "canon_hash": canon_hash,
        "statement_hash": stmt,
        "agent_id": cfg.agent_id or "unknown",
        "family": cfg.family or "A",
        "model_id": cfg.model_id or "unknown",
        "toolchain": {
            "lean": cfg.lean,
            "mathlib": "",
            "gate_image": cfg.gate_image or "",
        },
        "allowed_files": packet.allowed_files,
        "gate": {
            "local": "pass",
            "commands": stamp.get("commands") or [],
        },
        "proof_kind": proof_kind,
        "proof_object": packet.lean_declaration or packet.packet,
        "summary": "SUMMARY.md",
        "wall_time_s": 0,
        "notes": "",
    }
    dest = root / "CERTIFICATE.json"
    dest.write_text(json.dumps(cert, indent=2) + "\n", encoding="utf-8")
    print(f"wrote={dest}")
    print(f"skill_version={SKILL_VERSION}")
    print(f"statement_hash={stmt}")
    print(f"canon_hash={canon_hash}")
    return 0
