from __future__ import annotations

import sys

from rc.config import Config
from rc.github_api import GitHub, assignee_logins, label_names, split_repo
from rc.packet import now_utc, parse_issue_body, parse_time


def run(cfg: Config, argv: list[str]) -> int:
    if not cfg.token or not cfg.repo:
        print("GH_TOKEN and RC_REPO required", file=sys.stderr)
        return 1
    owner, repo = split_repo(cfg.repo)
    gh = GitHub(cfg.github_api, cfg.token)
    now = now_utc()
    for issue in gh.list_packet_issues(owner, repo):
        meta = parse_issue_body(issue.get("body") or "")
        labels = label_names(issue)
        until = parse_time(meta.get("claimed_until"))
        stale = "claimed" in labels and until is not None and until <= now
        print(
            f"packet={meta.get('packet') or '?'} issue={issue['number']} "
            f"claimed={'yes' if 'claimed' in labels else 'no'} "
            f"assignees={','.join(assignee_logins(issue)) or '-'} "
            f"until={meta.get('claimed_until') or '-'} "
            f"stale={'yes' if stale else 'no'}"
        )
    return 0
