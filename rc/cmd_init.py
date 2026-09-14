from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rc import SKILL_VERSION


def run(_cfg, argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="rc init")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--skill-version", default=SKILL_VERSION)
    args = parser.parse_args(argv)
    dest = Path.cwd() / ".rc"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "config.toml").write_text(
        f'repo = "{args.repo}"\nskill_version = "{args.skill_version}"\n',
        encoding="utf-8",
    )
    print(f"wrote={dest / 'config.toml'}")
    return 0
