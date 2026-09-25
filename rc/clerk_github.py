"""Call the Riemann Clerk GitHub App. No owner user token."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
import time
from typing import Any, Callable

from rc.clerk_pat import AGENTS_TEAM, BETA_TEAM, decide
from rc.http import HttpError, request

ORG = "MagratheaLab"
API = "https://api.github.com"
Fetch = Callable[..., Any]


def app_jwt(app_id: str, pem: str, now: int | None = None) -> str:
    """RS256 JWT for the GitHub App. PEM is not written to the repo."""
    stamp = int(time.time() if now is None else now)

    def b64(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    header = b64(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
    body = b64(
        json.dumps(
            {"iat": stamp - 60, "exp": stamp + 540, "iss": str(app_id)},
            separators=(",", ":"),
        ).encode()
    )
    signing = f"{header}.{body}".encode()
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=True) as handle:
        handle.write(pem)
        handle.flush()
        os.chmod(handle.name, 0o600)
        signed = subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", handle.name],
            input=signing,
            capture_output=True,
            check=True,
        )
    return f"{header}.{body}.{b64(signed.stdout)}"


def _teams(fetch: Fetch, login: str) -> list[str]:
    found = []
    for slug in (BETA_TEAM, AGENTS_TEAM):
        try:
            row = fetch(
                "GET",
                f"/orgs/{ORG}/teams/{slug}/memberships/{login}",
                None,
            )
        except HttpError as exc:
            if exc.status == 404:
                continue
            raise
        if isinstance(row, dict) and row.get("state") == "active":
            found.append(slug)
    return found


def _role(fetch: Fetch, login: str) -> str:
    try:
        row = fetch("GET", f"/orgs/{ORG}/memberships/{login}", None)
    except HttpError as exc:
        if exc.status == 404:
            return "absent"
        raise
    if not isinstance(row, dict) or row.get("state") != "active":
        return "absent"
    return str(row.get("role") or "member")


def apply_pending(fetch: Fetch, *, dry_run: bool = False) -> list[str]:
    """Approve or deny every pending fine-grained PAT request. Returns log lines."""
    listed = fetch("GET", f"/orgs/{ORG}/personal-access-token-requests?per_page=100", None)
    if not isinstance(listed, list):
        raise RuntimeError("PAT request list was not a list")
    lines: list[str] = []
    for raw in listed:
        if not isinstance(raw, dict) or "id" not in raw:
            continue
        request_id = raw["id"]
        login = str((raw.get("owner") or {}).get("login") or "")
        repos = fetch(
            "GET",
            f"/orgs/{ORG}/personal-access-token-requests/{request_id}/repositories?per_page=100",
            None,
        )
        if not isinstance(repos, list):
            repos = []
        view = dict(raw)
        view["repositories"] = repos
        view["teams"] = _teams(fetch, login) if login else []
        view["org_role"] = _role(fetch, login) if login else "absent"
        decision, reason = decide(view)
        if not dry_run:
            fetch(
                "POST",
                f"/orgs/{ORG}/personal-access-token-requests/{request_id}",
                {"action": decision, "reason": reason[:1024]},
            )
        lines.append(f"pat_request={request_id} user={login} {decision} {reason}")
    return lines


def live_fetch(token: str) -> Fetch:
    def fetch(method: str, path: str, payload: dict | None) -> Any:
        return request(API + path, method=method, token=token, payload=payload)

    return fetch


def installation_token(app_id: str, installation_id: str, pem: str) -> str:
    jwt = app_jwt(app_id, pem)
    issued = request(
        f"{API}/app/installations/{installation_id}/access_tokens",
        method="POST",
        token=jwt,
        payload={},
    )
    if not isinstance(issued, dict) or not issued.get("token"):
        raise RuntimeError("installation token missing")
    return str(issued["token"])
