"""GitHub Issues/PR client. Control plane. App not required for next/claim."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from rc.http import HttpError, request


class GitHub:
    def __init__(self, api: str, token: str):
        self.api = api.rstrip("/")
        self.token = token

    def _url(self, path: str) -> str:
        return f"{self.api}{path}"

    def get(self, path: str) -> Any:
        return request(self._url(path), token=self.token)

    def patch(self, path: str, payload: dict) -> Any:
        return request(self._url(path), method="PATCH", token=self.token, payload=payload)

    def post(self, path: str, payload: dict) -> Any:
        return request(self._url(path), method="POST", token=self.token, payload=payload)

    def user(self) -> dict:
        return self.get("/user")

    def login(self) -> str:
        if not self.token:
            raise RuntimeError("GH_TOKEN required")
        return self.user()["login"]

    def list_packet_issues(self, owner: str, repo: str) -> list[dict]:
        path = (
            f"/repos/{quote(owner)}/{quote(repo)}/issues"
            f"?state=open&labels=packet&per_page=100"
        )
        data = self.get(path)
        if not isinstance(data, list):
            raise RuntimeError("unexpected issues payload")
        return [i for i in data if "pull_request" not in i]

    def get_issue(self, owner: str, repo: str, number: int) -> dict:
        return self.get(f"/repos/{quote(owner)}/{quote(repo)}/issues/{number}")

    def comments(self, owner: str, repo: str, number: int) -> list[dict]:
        data = self.get(
            f"/repos/{quote(owner)}/{quote(repo)}/issues/{number}/comments?per_page=100"
        )
        return data if isinstance(data, list) else []

    def update_issue(self, owner: str, repo: str, number: int, payload: dict) -> dict:
        return self.patch(
            f"/repos/{quote(owner)}/{quote(repo)}/issues/{number}", payload
        )

    def create_issue(
        self, owner: str, repo: str, *, title: str, body: str, labels: list[str]
    ) -> dict:
        return self.post(
            f"/repos/{quote(owner)}/{quote(repo)}/issues",
            {"title": title, "body": body, "labels": labels},
        )

    def create_comment(self, owner: str, repo: str, number: int, body: str) -> dict:
        return self.post(
            f"/repos/{quote(owner)}/{quote(repo)}/issues/{number}/comments",
            {"body": body},
        )

    def list_issues(self, owner: str, repo: str, labels: str = "") -> list[dict]:
        q = f"?state=open&per_page=100"
        if labels:
            q += f"&labels={quote(labels, safe=',')}"
        data = self.get(f"/repos/{quote(owner)}/{quote(repo)}/issues{q}")
        return data if isinstance(data, list) else []

    def create_pr(
        self, owner: str, repo: str, *, title: str, head: str, base: str, body: str
    ) -> dict:
        return self.post(
            f"/repos/{quote(owner)}/{quote(repo)}/pulls",
            {"title": title, "head": head, "base": base, "body": body},
        )


def split_repo(repo: str) -> tuple[str, str]:
    repo = repo.strip().rstrip("/")
    if repo.endswith(".git"):
        repo = repo[:-4]
    if "github.com/" in repo:
        repo = repo.split("github.com/", 1)[1]
    parts = repo.split("/")
    if len(parts) < 2:
        raise ValueError(f"repo must be owner/name, got {repo!r}")
    return parts[0], parts[1]


def label_names(issue: dict) -> set[str]:
    names = set()
    for lab in issue.get("labels") or []:
        if isinstance(lab, dict):
            names.add(lab.get("name") or "")
        else:
            names.add(str(lab))
    names.discard("")
    return names


def assignee_logins(issue: dict) -> list[str]:
    out = []
    if issue.get("assignee") and issue["assignee"].get("login"):
        out.append(issue["assignee"]["login"])
    for person in issue.get("assignees") or []:
        login = person.get("login")
        if login and login not in out:
            out.append(login)
    return out
