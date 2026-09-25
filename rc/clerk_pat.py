"""Riemann Clerk: approve or deny one fine-grained PAT request.

The GitHub App is registered by the org owner. This module is the allowlist.
It does not merge, dispatch, or claim packets.
"""

from __future__ import annotations

WORLD_REPO = "riemann"
ALLOWED_WRITE = frozenset({"contents", "issues", "pull_requests"})
ALLOWED_READ = frozenset({"metadata"})


def _repo_names(request: dict) -> list[str]:
    names = []
    for repo in request.get("repositories") or []:
        if isinstance(repo, dict):
            names.append(repo.get("name") or repo.get("full_name") or "")
        else:
            names.append(str(repo))
    return [n.split("/")[-1] for n in names if n]


def decide(request: dict) -> tuple[str, str]:
    """Return ('approve'|'deny', reason)."""
    perms = request.get("permissions") or {}
    if not isinstance(perms, dict):
        return "deny", "permissions missing"
    extra = set(perms) - ALLOWED_WRITE - ALLOWED_READ
    if extra:
        return "deny", "permissions too wide: " + ",".join(sorted(extra))
    for key in ALLOWED_READ:
        if key in perms and perms[key] not in {"read", "none"}:
            return "deny", f"{key} must be read"
    for key in ALLOWED_WRITE:
        if perms.get(key) != "write":
            return "deny", f"{key} must be write"
    repos = _repo_names(request)
    if repos != [WORLD_REPO]:
        return "deny", f"repos must be exactly {WORLD_REPO}"
    selection = (request.get("repository_selection") or "subset").lower()
    if selection == "all":
        return "deny", "repository_selection all"
    return "approve", f"member PAT on {WORLD_REPO} only"
