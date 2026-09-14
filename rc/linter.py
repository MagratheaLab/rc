"""Local gates that do not need Docker: sorry, header freeze, notation, olean."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

BANNED = re.compile(
    r"\b(sorry|admit|native_decide|unsafe)\b", re.M
)
LOCAL_NOTATION = re.compile(r"(?m)^\s*local\s+notation\b")
AXIOM = re.compile(r"(?m)^\s*axiom\s+")
THEOREM_HEAD = re.compile(
    r"(?m)^(theorem|lemma|def|abbrev)\s+([A-Za-z0-9_'.]+)\s*.*"
)
OLEAN_NAMES = (".olean", ".ilean", ".trace")


def strip_lean_comments(src: str) -> str:
    src = re.sub(r"/-.*?-/", " ", src, flags=re.S)
    src = re.sub(r"--[^\n]*", " ", src)
    return src


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def declaration_header(src: str, short_name: str) -> str | None:
    """Return the first header line for declaration short_name (no module prefix)."""
    short = short_name.split(".")[-1]
    for match in THEOREM_HEAD.finditer(src):
        if match.group(2) == short or match.group(2).endswith("." + short):
            return match.group(0).rstrip()
    return None


def lint_lean_source(
    src: str,
    *,
    base_src: str | None = None,
    declaration: str = "",
) -> list[str]:
    errors: list[str] = []
    body = strip_lean_comments(src)
    if BANNED.search(body):
        errors.append("banned tactic: sorry/admit/native_decide/unsafe")
    if LOCAL_NOTATION.search(src):
        errors.append("local notation is forbidden (T-A2)")
    if AXIOM.search(body):
        errors.append("extra axiom is forbidden")
    if declaration and base_src is not None:
        old = declaration_header(base_src, declaration)
        new = declaration_header(src, declaration)
        if old and new and old != new:
            errors.append(f"theorem header rewrite: {old!r} -> {new!r}")
        if old and not new:
            errors.append(f"frozen declaration missing: {declaration}")
    return errors


def lint_paths(
    files: dict[str, str],
    *,
    base_files: dict[str, str] | None = None,
    declaration: str = "",
) -> list[str]:
    errors: list[str] = []
    for rel, src in files.items():
        lower = rel.lower()
        if lower.endswith(OLEAN_NAMES) or "/.lake/" in f"/{rel}" or rel.startswith(".lake/"):
            errors.append(f"compiled artifact in tree: {rel}")
            continue
        if not rel.endswith(".lean"):
            continue
        base = (base_files or {}).get(rel)
        errors.extend(
            f"{rel}: {e}"
            for e in lint_lean_source(
                src, base_src=base, declaration=declaration if base is not None else ""
            )
        )
    return errors


def statement_hash(src: str, declaration: str) -> str:
    header = declaration_header(src, declaration) or src
    return sha256_text(header + "\n")
