from __future__ import annotations

import sys
from urllib.parse import urlparse

from rc import LEAN_PIN, SKILL_VERSION
from rc.config import Config, gate_digest
from rc.http import HttpError, request


def fetch_skill(url: str) -> dict:
    data = request(url, timeout=20)
    if not isinstance(data, dict):
        raise RuntimeError("skill.json is not an object")
    return data


def run(cfg: Config) -> int:
    errors: list[str] = []
    host = (urlparse(cfg.github_api).hostname or "").lower()
    if host in {"127.0.0.1", "localhost"} and not cfg.github_api:
        errors.append("localhost dispatcher is not the control plane")

    skill = None
    try:
        skill = fetch_skill(cfg.core_skill_url)
    except (HttpError, RuntimeError, OSError) as exc:
        errors.append(f"skill.json missing: {exc}")

    version = None
    if skill is not None:
        version = skill.get("version")
        if not version:
            errors.append("skill tag missing: skill.json has no version")
        else:
            version = str(version)

    digest = gate_digest(cfg.gate_image)
    if not digest:
        errors.append("gate image unpinned (need name@sha256:64hex)")

    print(f"skill_expected={SKILL_VERSION}")
    print(f"skill_version={version or 'MISSING'}")
    print("skill_ref=main (until tag v0.1.4)")
    print(f"lean={cfg.lean or LEAN_PIN}")
    print(f"gate_image={cfg.gate_image or 'MISSING'}")
    print(f"github_api={cfg.github_api}")
    print(f"github_token={'set' if cfg.token else 'missing'}")
    print("moltbook=not_used")
    print("dispatcher_localhost=not_used")
    print("fixture=P-20260914-fx01")
    if errors:
        for err in errors:
            print(f"DOCTOR_FAIL {err}", file=sys.stderr)
        return 1
    print("DOCTOR_OK")
    return 0
