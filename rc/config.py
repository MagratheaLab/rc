"""Env + optional .rc/config.toml. No Moltbook. No localhost dispatcher."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from rc import LEAN_PIN, SKILL_VERSION

CORE_SKILL_MAIN = (
    "https://raw.githubusercontent.com/MagratheaLab/core/"
    "main/published-skills/skill.json"
)
DEFAULT_GITHUB_API = "https://api.github.com"
PIN_PATH = Path(__file__).resolve().parent.parent / "gate" / "pin.json"


@dataclass
class Config:
    repo: str
    github_api: str
    token: str
    core_skill_url: str
    gate_image: str
    family: str
    agent_id: str
    model_id: str
    skill_version: str
    lean: str
    world: Path | None
    lake_mode: str


def _walk_toml() -> dict:
    here = Path.cwd().resolve()
    for folder in [here, *here.parents]:
        path = folder / ".rc" / "config.toml"
        if path.is_file():
            return tomllib.loads(path.read_text(encoding="utf-8"))
    return {}


def _pin_image() -> str:
    if not PIN_PATH.is_file():
        return ""
    import json

    data = json.loads(PIN_PATH.read_text(encoding="utf-8"))
    digest = (data.get("digest") or "").strip()
    image = data.get("image") or "magrathea-gate"
    tag = data.get("tag") or "lean-4.33.0"
    name = f"{image}:{tag}"
    if digest.startswith("sha256:") and len(digest) == 71:
        return f"{name}@{digest}"
    return ""


def load() -> Config:
    file_cfg = _walk_toml()
    env = os.environ
    repo = env.get("RC_REPO") or file_cfg.get("repo") or ""
    image = env.get("RC_GATE_IMAGE") or file_cfg.get("gate_image") or _pin_image()
    world = env.get("RC_WORLD")
    return Config(
        repo=repo,
        github_api=(
            env.get("RC_GITHUB_API")
            or file_cfg.get("github_api")
            or DEFAULT_GITHUB_API
        ).rstrip("/"),
        token=(
            env.get("RC_GITHUB_TOKEN")
            or env.get("GH_TOKEN")
            or env.get("GITHUB_TOKEN")
            or file_cfg.get("token")
            or ""
        ),
        core_skill_url=(
            env.get("RC_CORE_SKILL_URL")
            or file_cfg.get("core_skill_url")
            or CORE_SKILL_MAIN
        ),
        gate_image=image,
        family=env.get("RC_FAMILY") or file_cfg.get("family") or "",
        agent_id=env.get("RC_AGENT_ID") or file_cfg.get("agent_id") or "",
        model_id=env.get("RC_MODEL_ID") or file_cfg.get("model_id") or "",
        skill_version=SKILL_VERSION,
        lean=env.get("RC_LEAN") or file_cfg.get("lean") or LEAN_PIN,
        lake_mode=(env.get("RC_LAKE_MODE") or file_cfg.get("lake_mode") or "docker").lower(),
        world=Path(world).resolve() if world else None,
    )


def gate_digest(image: str) -> str | None:
    if not image:
        return None
    if "@sha256:" not in image:
        return None
    digest = image.split("@", 1)[1].strip()
    if digest.startswith("sha256:") and len(digest) == 71 and all(
        c in "0123456789abcdef" for c in digest[7:]
    ):
        return digest
    return None
