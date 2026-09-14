"""Packet markdown + GitHub issue body (YAML-ish front matter)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from rc import CLAIM_TYPES

FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\s*(.*)\Z", re.S)


@dataclass
class Packet:
    packet: str
    priority: str = "P2"
    claim_type: str = "lemma"
    ttl: str = "24h"
    family: str = ""
    lean_declaration: str = ""
    skill_version: str = "0.1.4"
    allowed_files: list[str] = field(default_factory=list)
    canon_hash: str = ""
    goal: str = ""
    source: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def path(self) -> str:
        return f"packets/{self.packet}.md"


def parse_kv_block(text: str) -> dict[str, Any]:
    """Parse a YAML-ish block: key: value, or key: followed by indented list."""
    data: dict[str, Any] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue
        if line.startswith(" ") or line.startswith("\t"):
            i += 1
            continue
        if ":" not in line:
            i += 1
            continue
        key, rest = line.split(":", 1)
        key = key.strip()
        rest = rest.strip()
        if rest in {"", "|", ">"}:
            items: list[str] = []
            i += 1
            while i < len(lines) and (
                lines[i].startswith("  - ") or lines[i].startswith("    - ")
            ):
                items.append(lines[i].split("-", 1)[1].strip())
                i += 1
            data[key] = items
            continue
        if rest.startswith("[") and rest.endswith("]"):
            inner = rest[1:-1].strip()
            data[key] = [p.strip() for p in inner.split(",") if p.strip()] if inner else []
        else:
            if (rest.startswith('"') and rest.endswith('"')) or (
                rest.startswith("'") and rest.endswith("'")
            ):
                rest = rest[1:-1]
            data[key] = rest
        i += 1
    return data


def parse_packet_markdown(text: str, *, source: str = "") -> Packet:
    match = FRONT_MATTER.match(text.strip() + ("\n" if not text.endswith("\n") else ""))
    if match:
        body_meta, _notes = match.group(1), match.group(2)
        meta = parse_kv_block(body_meta)
    else:
        meta = parse_kv_block(text)
    pid = str(meta.get("id") or meta.get("packet") or "").strip()
    if not pid:
        raise ValueError("packet id missing")
    allowed = meta.get("allowed_files") or []
    if isinstance(allowed, str):
        allowed = [allowed]
    claim = str(meta.get("claim_type") or "lemma")
    if claim not in CLAIM_TYPES:
        raise ValueError(f"bad claim_type: {claim}")
    return Packet(
        packet=pid,
        priority=str(meta.get("priority") or "P2"),
        claim_type=claim,
        ttl=str(meta.get("ttl") or "24h"),
        family=str(meta.get("family") or ""),
        lean_declaration=str(meta.get("lean_declaration") or ""),
        skill_version=str(meta.get("skill_version") or "0.1.4"),
        allowed_files=[str(p) for p in allowed],
        canon_hash=str(meta.get("canon_hash") or ""),
        goal=str(meta.get("goal") or ""),
        source=source,
        extra=meta,
    )


def parse_issue_body(body: str) -> dict[str, str]:
    """First YAML-ish keys of a GitHub issue body (DECISIONS.md schema)."""
    if not body:
        return {}
    head = body.split("\n\n", 1)[0]
    keys = parse_kv_block(head)
    out: dict[str, str] = {}
    for key, val in keys.items():
        if isinstance(val, list):
            out[key] = ",".join(val)
        else:
            out[key] = str(val)
    return out


def parse_ttl(spec: str) -> timedelta:
    spec = (spec or "24h").strip().lower()
    match = re.fullmatch(r"(\d+)\s*h(ours?)?", spec)
    if match:
        return timedelta(hours=int(match.group(1)))
    match = re.fullmatch(r"(\d+)\s*m(in(utes?)?)?", spec)
    if match:
        return timedelta(minutes=int(match.group(1)))
    return timedelta(hours=24)


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_packet_file(world: Path, packet_id: str) -> Packet:
    path = world / "packets" / f"{packet_id}.md"
    if not path.is_file():
        raise FileNotFoundError(f"missing {path}")
    return parse_packet_markdown(path.read_text(encoding="utf-8"), source=str(path))
