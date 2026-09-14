"""Tiny JSON HTTP client. Stdlib only. Refuses moltbook hosts."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

MOLTBOOK_HOSTS = {"moltbook.com", "www.moltbook.com"}


class HttpError(RuntimeError):
    def __init__(self, status: int, url: str, body: str):
        super().__init__(f"HTTP {status} {url}: {body[:300]}")
        self.status = status
        self.url = url
        self.body = body


def _check_host(url: str) -> None:
    host = (urlparse(url).hostname or "").lower()
    if host in MOLTBOOK_HOSTS:
        raise RuntimeError("protocol_violation: moltbook is not a control plane")


def request(
    url: str,
    *,
    method: str = "GET",
    token: str = "",
    payload: Any | None = None,
    timeout: int = 20,
) -> Any:
    _check_host(url)
    data = None
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "magrathea-rc"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise HttpError(exc.code, url, body) from exc
