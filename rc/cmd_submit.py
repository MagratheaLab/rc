from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from rc.config import Config
from rc.delivery import check_tree
from rc.github_api import GitHub, split_repo
from rc.packet import load_packet_file
from rc.state import find_world, work_dir


def _git(world: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(world), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def run(cfg: Config, argv: list[str]) -> int:
    packet_id = next((a for a in argv if a.startswith("P-")), "")
    dry = "--dry-run" in argv
    world = find_world(cfg.world)
    if not packet_id:
        print("usage: rc submit P-...", file=sys.stderr)
        return 2
    packet = load_packet_file(world, packet_id)
    work = work_dir(world, packet_id)
    overlay = work if work.is_dir() else world
    for name in ("CERTIFICATE.json", "SUMMARY.md"):
        if not (overlay / name).is_file():
            print(f"submit requires {name}", file=sys.stderr)
            return 1
    stamp = world / ".rc" / f"gate-{packet.packet}.json"
    if not stamp.is_file():
        print("submit requires a passing rc gate stamp", file=sys.stderr)
        return 1
    import json

    if not json.loads(stamp.read_text(encoding="utf-8")).get("pass"):
        print("gate stamp is fail", file=sys.stderr)
        return 1

    # Copy overlay files into world working tree (not via main).
    branch = f"packet/{packet.packet}"
    changed = []
    for path in overlay.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(overlay).as_posix()
        dest = world / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(path.read_bytes())
        changed.append(rel)
    errors = check_tree(world, packet, changed, require_delivery=True)
    if errors:
        for err in errors:
            print(f"SUBMIT_FAIL {err}", file=sys.stderr)
        return 1
    if dry:
        print(f"branch={branch}")
        print("dry-run=ok")
        return 0
    if not cfg.token or not cfg.repo:
        print("GH_TOKEN and RC_REPO required to open a PR", file=sys.stderr)
        return 1

    _git(world, "checkout", "main")
    created = _git(world, "checkout", "-B", branch)
    if created.returncode != 0:
        print(created.stderr, file=sys.stderr)
        return 1
    files = list(packet.allowed_files) + ["CERTIFICATE.json", "SUMMARY.md"]
    add = _git(world, "add", "--", *files)
    if add.returncode != 0:
        print(add.stderr, file=sys.stderr)
        return 1
    commit = _git(
        world,
        "commit",
        "-m",
        f"{packet.packet}: fixture delivery",
    )
    if commit.returncode != 0:
        print(commit.stderr or commit.stdout, file=sys.stderr)
        return 1
    push = _git(world, "push", "-u", "origin", branch)
    if push.returncode != 0:
        print(push.stderr, file=sys.stderr)
        return 1
    owner, repo = split_repo(cfg.repo)
    gh = GitHub(cfg.github_api, cfg.token)
    pr = gh.create_pr(
        owner,
        repo,
        title=f"{packet.packet}",
        head=branch,
        base="main",
        body=f"Packet {packet.packet}\nclaim_type: {packet.claim_type}\n",
    )
    print(f"pr={pr.get('html_url') or pr.get('number')}")
    print("pushed_main=no")
    return 0
