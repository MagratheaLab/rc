from __future__ import annotations

import re
import sys

from rc import PRIORITY_RANK
from rc.config import Config
from rc.github_api import GitHub, assignee_logins, label_names, split_repo
from rc.packet import parse_issue_body

HERMES_ASSIGN = re.compile(
    r"HERMES_ASSIGN\s+agent=(?P<agent>\S+)(?:\s+family=(?P<family>\S+))?"
)


def _rank(priority: str) -> int:
    return PRIORITY_RANK.get(priority.upper(), 99)


def _issue_packet(issue: dict) -> dict:
    meta = parse_issue_body(issue.get("body") or "")
    pid = meta.get("packet") or ""
    if not pid and (issue.get("title") or "").startswith("P-"):
        pid = issue["title"].split()[0]
    meta["packet"] = pid
    meta.setdefault("priority", "P2")
    meta.setdefault("claim_type", "lemma")
    meta.setdefault("ttl", "24h")
    return meta


def select_issue(issues: list[dict], comments_by_number: dict[int, list[dict]], agent_id: str) -> dict | None:
    assigned = []
    for issue in issues:
        if "packet" not in label_names(issue):
            continue
        for comment in comments_by_number.get(issue["number"], []):
            match = HERMES_ASSIGN.search(comment.get("body") or "")
            if match and agent_id and match.group("agent") == agent_id:
                assigned.append(issue)
                break
    pool = assigned or [
        i for i in issues if "packet" in label_names(i) and "claimed" not in label_names(i)
    ]
    if not pool:
        # still offer a claimed packet? next should pick open unclaimed, or assigned.
        return None

    def key(issue: dict) -> tuple:
        meta = _issue_packet(issue)
        return (_rank(meta.get("priority") or "P2"), issue["number"])

    return sorted(pool, key=key)[0]


def run(cfg: Config, argv: list[str]) -> int:
    if not cfg.token:
        print("GH_TOKEN required for rc next", file=sys.stderr)
        return 1
    if not cfg.repo:
        print("RC_REPO=owner/name required", file=sys.stderr)
        return 1
    owner, repo = split_repo(cfg.repo)
    gh = GitHub(cfg.github_api, cfg.token)
    issues = gh.list_packet_issues(owner, repo)
    comments = {}
    if cfg.agent_id:
        for issue in issues:
            comments[issue["number"]] = gh.comments(owner, repo, issue["number"])
    chosen = select_issue(issues, comments, cfg.agent_id)
    if not chosen:
        print("packet=none")
        return 0
    meta = _issue_packet(chosen)
    print(f"packet={meta['packet']}")
    print(f"issue={owner}/{repo}#{chosen['number']}")
    print(f"priority={meta.get('priority')}")
    print(f"claim_type={meta.get('claim_type')}")
    print(f"ttl={meta.get('ttl') or '24h'}")
    if meta.get("lean_declaration"):
        print(f"lean_declaration={meta['lean_declaration']}")
    print(f"labels={','.join(sorted(label_names(chosen)))}")
    assignees = assignee_logins(chosen)
    if assignees:
        print(f"assignees={','.join(assignees)}")
    return 0
