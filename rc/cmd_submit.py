from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from rc.branch import allowed_lock_conflict, check_packet_id, packet_branch
from rc.config import Config
from rc.delivery import check_tree, receipt_files
from rc.github_api import GitHub, label_names, split_repo
from rc.packet import load_packet_file
from rc.state import find_world, work_dir


def pr_body(packet_id: str, claim_type: str, issue_number: int | None) -> str:
    lines = [f"Packet {packet_id}", f"claim_type: {claim_type}"]
    if issue_number:
        lines.append(f"Closes #{issue_number}")
    return "\n".join(lines) + "\n"


_ASKPASS = r"""#!/bin/sh
case "$1" in
  *[Uu]sername*) echo x-access-token ;;
  *) echo "$RC_GIT_ASKPASS_TOKEN" ;;
esac
"""


def _git(
    world: Path, *args: str, token: str | None = None
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    tmp = None
    if token:
        tmp = tempfile.NamedTemporaryFile("w", delete=False, prefix="rc-askpass-")
        tmp.write(_ASKPASS)
        tmp.close()
        os.chmod(tmp.name, stat.S_IRWXU)
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GIT_ASKPASS"] = tmp.name
        env["RC_GIT_ASKPASS_TOKEN"] = token
        env["GCM_INTERACTIVE"] = "never"
    try:
        return subprocess.run(
            ["git", "-C", str(world), *args],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass


def run(cfg: Config, argv: list[str]) -> int:
    packet_id = next((a for a in argv if a.startswith("P-")), "")
    dry = "--dry-run" in argv
    world = find_world(cfg.world)
    if not packet_id:
        print("usage: rc submit P-...", file=sys.stderr)
        return 2
    bad_id = check_packet_id(packet_id)
    if bad_id:
        print(f"SUBMIT_FAIL {bad_id}", file=sys.stderr)
        return 1
    packet = load_packet_file(world, packet_id)
    work = work_dir(world, packet_id)
    overlay = work if work.is_dir() else world
    cert_rel, sum_rel = receipt_files(packet.packet)
    for name in (cert_rel, sum_rel):
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
    branch = packet_branch(packet.packet)
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

    owner, repo = split_repo(cfg.repo)
    gh = GitHub(cfg.github_api, cfg.token)
    open_prs = []
    for item in gh.list_open_prs(owner, repo):
        files = gh.pr_files(owner, repo, int(item.get("number") or 0))
        open_prs.append(
            {
                "number": item.get("number"),
                "head": item.get("head") or {},
                "html_url": item.get("html_url"),
                "files": [f.get("filename") or "" for f in files],
            }
        )
    lock = allowed_lock_conflict(open_prs, packet.packet, list(packet.allowed_files))
    if lock:
        print(f"SUBMIT_FAIL {lock}", file=sys.stderr)
        return 1
    existing = next(
        (p for p in open_prs if ((p.get("head") or {}).get("ref") or "") == branch),
        None,
    )

    _git(world, "checkout", "main")
    created = _git(world, "checkout", "-B", branch)
    if created.returncode != 0:
        print(created.stderr, file=sys.stderr)
        return 1
    files = list(packet.allowed_files) + [cert_rel, sum_rel]
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
    push = _git(world, "push", "-u", "origin", branch, token=cfg.token)
    if push.returncode != 0:
        print(push.stderr, file=sys.stderr)
        return 1
    issue_number = None
    issue = None
    try:
        from rc.cmd_claim import find_packet_issue

        issue = find_packet_issue(gh, owner, repo, packet.packet)
        issue_number = int(issue["number"])
    except RuntimeError:
        pass
    if existing:
        pr = existing
    else:
        pr = gh.create_pr(
            owner,
            repo,
            title=f"{packet.packet}",
            head=branch,
            base="main",
            body=pr_body(packet.packet, packet.claim_type, issue_number),
        )
    if issue is not None and issue_number is not None:
        labels = sorted(label_names(issue) | {"packet", "in-review"})
        gh.update_issue(owner, repo, issue_number, {"labels": labels})
    print(f"pr={pr.get('html_url') or pr.get('number')}")
    if issue_number:
        print(f"closes=#{issue_number}")
    print("pushed_main=no")
    return 0
