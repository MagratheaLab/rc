"""Riemann Clerk: approve or deny one fine-grained PAT request.

The GitHub App is registered by the org owner. This module is the allowlist.
It does not merge, dispatch, or claim packets.
"""

from __future__ import annotations

WORLD_REPO = "riemann"
REVIEW_REPO = "riemann-reviews"
BETA_TEAM = "riemann-betatester-group01"
AGENTS_TEAM = "agents"
ALLOWED_WRITE = frozenset({"contents", "issues", "pull_requests"})
ALLOWED_READ = frozenset({"metadata"})
BETA_PERMS = {
    "contents": "read",
    "issues": "write",
    "pull_requests": "read",
    "metadata": "read",
}


def _repo_names(request: dict) -> list[str]:
    names = []
    for repo in request.get("repositories") or []:
        if isinstance(repo, dict):
            names.append(repo.get("name") or repo.get("full_name") or "")
        else:
            names.append(str(repo))
    return [n.split("/")[-1] for n in names if n]


def _repository_permissions(perms: object) -> tuple[dict | None, str]:
    """Flatten GitHub's nested permissions. Deny org-level or account permissions."""
    if not isinstance(perms, dict):
        return None, "permissions missing"
    if any(key in perms for key in ("repository", "organization", "other")):
        if perms.get("organization") or perms.get("other"):
            return None, "org or account permissions"
        repo = perms.get("repository") or {}
        if not isinstance(repo, dict):
            return None, "permissions missing"
        return repo, ""
    return perms, ""


def _teams(request: dict) -> set[str] | None:
    raw = request.get("teams")
    if raw is None:
        return None
    return {str(name) for name in raw}


def _worker_shape(perms: dict, repos: list[str], selection: str) -> str | None:
    if selection == "all":
        return "repository_selection all"
    extra = set(perms) - ALLOWED_WRITE - ALLOWED_READ
    if extra:
        return "permissions too wide: " + ",".join(sorted(extra))
    for key in ALLOWED_READ:
        if key in perms and perms[key] not in {"read", "none"}:
            return f"{key} must be read"
    for key in ALLOWED_WRITE:
        if perms.get(key) != "write":
            return f"{key} must be write"
    if repos != [WORLD_REPO]:
        return f"repos must be exactly {WORLD_REPO}"
    return None


def _beta_shape(perms: dict, repos: list[str], selection: str) -> bool:
    if selection == "all":
        return False
    if set(repos) != {WORLD_REPO, REVIEW_REPO}:
        return False
    if set(perms) - set(BETA_PERMS):
        return False
    for key, required in BETA_PERMS.items():
        if key == "metadata" and key not in perms:
            continue
        if perms.get(key) != required:
            return False
    return True


def decide(request: dict) -> tuple[str, str]:
    """Return ('approve'|'deny', reason).

    ``teams`` absent keeps the original worker allowlist (unit tests, Ford).
    When ``teams`` is present, the beta group only gets the reviewer shape.
    """
    if request.get("org_role") == "admin":
        return "deny", "owner"
    perms, err = _repository_permissions(request.get("permissions") or {})
    if perms is None:
        return "deny", err or "permissions missing"
    repos = _repo_names(request)
    selection = (request.get("repository_selection") or "subset").lower()
    teams = _teams(request)
    worker_err = _worker_shape(perms, repos, selection)
    if worker_err is None:
        if teams is not None and BETA_TEAM in teams and AGENTS_TEAM not in teams:
            return "deny", "beta group is not a worker token"
        return "approve", f"member PAT on {WORLD_REPO} only"
    if _beta_shape(perms, repos, selection):
        if teams is None or BETA_TEAM not in teams:
            return "deny", f"beta reviewer token requires team {BETA_TEAM}"
        return "approve", f"beta reviewer on {WORLD_REPO} and {REVIEW_REPO}"
    if selection == "all":
        return "deny", "repository_selection all"
    if worker_err.startswith("permissions") or worker_err.startswith("org"):
        return "deny", worker_err
    return "deny", worker_err
