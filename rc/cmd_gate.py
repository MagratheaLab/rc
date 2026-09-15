from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from rc.config import Config
from rc.delivery import check_tree
from rc.linter import lint_paths, sha256_text
from rc.packet import load_packet_file
from rc.state import find_world, load_state, work_dir


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _collect_lean(root: Path, rels: list[str]) -> dict[str, str]:
    out = {}
    for rel in rels:
        path = root / rel
        if path.is_file():
            out[rel] = _read(path)
    return out


def _changed_files(world: Path, work: Path) -> list[str]:
    changed = []
    for path in work.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(work).as_posix()
        base = world / rel
        if not base.is_file() or base.read_bytes() != path.read_bytes():
            changed.append(rel)
    for name in ("CERTIFICATE.json", "SUMMARY.md"):
        if (work / name).is_file() or (world / name).is_file():
            src = work / name if (work / name).is_file() else world / name
            base_ok = False
            # delivery files are always "in the PR"
            if src.is_file():
                changed.append(name)
    # unique preserve order
    seen = set()
    uniq = []
    for item in changed:
        if item not in seen:
            seen.add(item)
            uniq.append(item)
    return uniq


def _docker_available() -> bool:
    try:
        subprocess.run(
            ["docker", "info"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=8,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _docker_run_ref(image: str) -> str:
    """Registry pins: name@sha256:manifest. Local GHA ids: run by image id."""
    if "@" not in image:
        return image
    name, digest = image.split("@", 1)
    host = name.split("/")[0].split(":")[0]
    if "." in host or host == "localhost":
        return image
    if digest.startswith("sha256:"):
        return digest
    return name or image


def _run_lake_docker(image: str, src: Path, target: str) -> tuple[int, str]:
    run_image = _docker_run_ref(image)
    cmd = [
        "docker",
        "run",
        "--rm",
        "--network=none",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,exec,mode=1777",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--memory",
        "2g",
        "--cpus",
        "2",
        "--pids-limit",
        "256",
        "-v",
        f"{src}:/repo:ro",
        run_image,
        "bash",
        "-c",
        # Login bash (-l) drops image PATH so lake is missing. cap-drop ALL
        # forbids preserving ownership on copy.
        "export PATH=/usr/local/elan/bin:$PATH; "
        "cp -R --no-preserve=ownership /repo /tmp/src && cd /tmp/src && lake build "
        + subprocess.list2cmdline([target]),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out


def run(cfg: Config, argv: list[str]) -> int:
    # Worker `rc gate` on GHA must not require CERTIFICATE; world CI passes --ci.
    ci = "--ci" in argv
    world = find_world(cfg.world)
    # Packet id: argv or the only state file.
    packet_id = next((a for a in argv if a.startswith("P-")), "")
    if not packet_id:
        states = list((world / ".rc").glob("state-P-*.json")) if (world / ".rc").is_dir() else []
        if len(states) == 1:
            packet_id = states[0].name[len("state-") : -len(".json")]
        else:
            print("usage: rc gate P-...", file=sys.stderr)
            return 2

    packet = load_packet_file(world, packet_id)
    work = work_dir(world, packet_id)
    overlay_root = work if work.is_dir() else world

    files = _collect_lean(overlay_root, packet.allowed_files)
    if not files:
        files = _collect_lean(world, packet.allowed_files)
    base_files = _collect_lean(world, packet.allowed_files)
    # If overlay differs, lint overlay against world (main) headers.
    errors = lint_paths(
        files, base_files=base_files, declaration=packet.lean_declaration
    )

    # Reject olean anywhere under overlay or staged world.
    for root in {overlay_root, world}:
        for path in root.rglob("*"):
            if path.suffix in {".olean", ".ilean"} or path.name == ".lake" or ".lake" in path.parts:
                if path.is_file() and ".git" not in path.parts:
                    rel = path.relative_to(root).as_posix()
                    if rel.startswith(".rc/"):
                        continue
                    errors.append(f"compiled artifact in tree: {rel}")

    lake_exit = None
    lake_out = ""
    lake_ran = False
    lake_mode = cfg.lake_mode if cfg.lake_mode in {"docker", "ci"} else "docker"
    if not errors and packet.claim_type == "lemma" and lake_mode == "ci":
        print("lake=ci (canonical judge is world GitHub Action)")
    elif not errors and packet.claim_type == "lemma":
        if not cfg.gate_image:
            errors.append("gate image unpinned")
        elif not _docker_available():
            errors.append("docker required for lemma gate (lake build)")
        else:
            lake_ran = True
            with tempfile.TemporaryDirectory(prefix="rc-gate-") as tmp:
                tmp_path = Path(tmp)
                # Full world + overlay of work files (allowed + delivery).
                shutil.copytree(
                    world,
                    tmp_path / "src",
                    ignore=shutil.ignore_patterns(
                        ".git", ".rc", ".lake", "*.olean", "*.ilean"
                    ),
                    dirs_exist_ok=False,
                )
                src = tmp_path / "src"
                if work.is_dir():
                    for path in work.rglob("*"):
                        if path.is_file():
                            rel = path.relative_to(work)
                            dest = src / rel
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(path, dest)
                target = packet.extra.get("local_gates")
                lake_target = "RiemannCanon"
                if packet.lean_declaration:
                    lake_target = packet.lean_declaration.split(".")[0]
                lake_exit, lake_out = _run_lake_docker(cfg.gate_image, src, lake_target)
                if lake_exit != 0:
                    tail = " ".join(lake_out.strip().splitlines()[-8:])[:800]
                    extra = f": {tail}" if tail else ""
                    errors.append(f"lake build failed exit={lake_exit}{extra}")

    changed = _changed_files(world, overlay_root) if overlay_root != world else []
    if overlay_root == world:
        # CI on a PR checkout: treat tracked delivery + allowed as the tree.
        changed = [
            p.relative_to(world).as_posix()
            for p in world.rglob("*")
            if p.is_file() and ".git" not in p.parts and ".rc" not in p.parts
        ]
    require_delivery = ci
    errors.extend(
        check_tree(overlay_root if overlay_root.is_dir() else world, packet, changed, require_delivery=require_delivery)
    )
    # CERTIFICATE/SUMMARY live at world root in CI checkouts.
    if overlay_root != world and ci:
        errors.extend(
            check_tree(world, packet, changed, require_delivery=True)
        )

    payload = {
        "packet": packet.packet,
        "linter": "fail" if any("sorry" in e or "header" in e or "notation" in e or "axiom" in e or "banned" in e for e in errors) else "pass",
        "commands": [f"lake build {packet.lean_declaration.split('.')[0] if packet.lean_declaration else 'RiemannCanon'}"],
        "lake_exit": lake_exit,
        "declaration": packet.lean_declaration,
        "errors": errors,
    }
    ident = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = sha256_text(ident)
    print(f"packet={packet.packet}")
    print(f"gate={'fail' if errors else 'pass'}")
    print(f"gate_hash={digest}")
    if lake_ran:
        print(f"lake_exit={lake_exit}")
    for err in errors:
        print(f"GATE_FAIL {err}", file=sys.stderr)
    stamp = {
        "pass": not errors,
        "hash": digest,
        "errors": errors,
        "commands": payload["commands"],
        "lake_exit": lake_exit,
        "lake_mode": lake_mode,
    }
    stamp_path = world / ".rc" / f"gate-{packet.packet}.json"
    stamp_path.parent.mkdir(parents=True, exist_ok=True)
    stamp_path.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    return 1 if errors else 0
