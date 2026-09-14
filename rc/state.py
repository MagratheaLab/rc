from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def rc_dir(world: Path) -> Path:
    path = world / ".rc"
    path.mkdir(parents=True, exist_ok=True)
    return path


def work_dir(world: Path, packet_id: str) -> Path:
    return rc_dir(world) / "work" / packet_id


def state_path(world: Path, packet_id: str) -> Path:
    return rc_dir(world) / f"state-{packet_id}.json"


def save_state(world: Path, packet_id: str, data: dict[str, Any]) -> Path:
    path = state_path(world, packet_id)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def load_state(world: Path, packet_id: str) -> dict[str, Any]:
    path = state_path(world, packet_id)
    if not path.is_file():
        raise FileNotFoundError(f"no state for {packet_id}; run rc work first")
    return json.loads(path.read_text(encoding="utf-8"))


def find_world(explicit: Path | None) -> Path:
    if explicit:
        return explicit.resolve()
    here = Path.cwd().resolve()
    for folder in [here, *here.parents]:
        if (folder / "packets").is_dir() and (folder / ".git").exists():
            return folder
        if (folder / ".rc" / "config.toml").is_file() and (folder / "packets").is_dir():
            return folder
    raise FileNotFoundError("not inside a Magrathea world repo (packets/ + git)")
