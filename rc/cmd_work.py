from __future__ import annotations

import shutil
import sys
from pathlib import Path

from rc.config import Config
from rc.packet import load_packet_file
from rc.state import find_world, save_state, work_dir


def _copy_into(world: Path, dest: Path, rel: str) -> None:
    src = world / rel
    if not src.is_file():
        raise FileNotFoundError(f"allowed file missing in world: {rel}")
    target = dest / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)


def run(cfg: Config, argv: list[str]) -> int:
    if not argv:
        print("usage: rc work P-...", file=sys.stderr)
        return 2
    packet_id = argv[0]
    world = find_world(cfg.world)
    packet = load_packet_file(world, packet_id)
    dest = work_dir(world, packet_id)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    copies = list(packet.allowed_files) + [packet.path]
    for rel in copies:
        _copy_into(world, dest, rel)

    # T1: nothing else may be present.
    present = sorted(
        p.relative_to(dest).as_posix()
        for p in dest.rglob("*")
        if p.is_file()
    )
    save_state(
        world,
        packet_id,
        {
            "packet": packet.packet,
            "world": str(world),
            "work": str(dest),
            "allowed_files": packet.allowed_files,
            "claim_type": packet.claim_type,
            "lean_declaration": packet.lean_declaration,
            "skill_version": packet.skill_version,
            "priority": packet.priority,
            "repo": cfg.repo,
        },
    )
    print(f"packet={packet.packet}")
    print(f"work={dest}")
    print(f"files={','.join(present)}")
    return 0
