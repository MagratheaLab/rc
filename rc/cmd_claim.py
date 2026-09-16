from __future__ import annotations

import sys

from rc import CLAIM_TYPES, PRIORITY_RANK
from rc.config import Config
from rc.github_api import GitHub, assignee_logins, label_names, split_repo
from rc.packet import iso, now_utc, parse_issue_body, parse_time, parse_ttl


def _set_body_keys(body: str, updates: dict[str, str]) -> str:
    lines = (body or "").splitlines()
    seen = set()
    out = []
    for line in lines:
        if ":" in line and not line.startswith((" ", "\t")):
            key = line.split(":", 1)[0].strip()
            if key in updates:
                out.append(f"{key}: {updates[key]}")
                seen.add(key)
                continue
        out.append(line)
    # Insert missing keys at the top of the YAML-ish block.
    missing = [f"{k}: {v}" for k, v in updates.items() if k not in seen]
    if missing:
        # After last leading key or at start.
        insert_at = 0
        for i, line in enumerate(out):
            if line.strip() == "":
                insert_at = i
                break
            if ":" in line:
                insert_at = i + 1
        out = out[:insert_at] + missing + out[insert_at:]
    return "\n".join(out).rstrip() + "\n"


def find_packet_issue(gh: GitHub, owner: str, repo: str, packet_id: str) -> dict:
    for issue in gh.list_packet_issues(owner, repo):
        meta = parse_issue_body(issue.get("body") or "")
        pid = meta.get("packet") or ""
        if pid == packet_id or (issue.get("title") or "").startswith(packet_id):
            return issue
    raise RuntimeError(f"no open packet issue for {packet_id}")


def run(cfg: Config, argv: list[str]) -> int:
    if not argv:
        print("usage: rc claim P-...", file=sys.stderr)
        return 2
    packet_id = argv[0]
    if not cfg.token or not cfg.repo:
        print("GH_TOKEN and RC_REPO required", file=sys.stderr)
        return 1
    owner, repo = split_repo(cfg.repo)
    gh = GitHub(cfg.github_api, cfg.token)
    login = gh.login()
    issue = find_packet_issue(gh, owner, repo, packet_id)
    number = issue["number"]
    labels = label_names(issue)
    meta = parse_issue_body(issue.get("body") or "")
    ttl = parse_ttl(meta.get("ttl") or "24h")
    until = parse_time(meta.get("claimed_until"))
    holders = assignee_logins(issue)
    claimed = "claimed" in labels
    now = now_utc()
    if claimed and until and until > now and holders and login not in holders:
        print(
            f"CLAIM_FAIL packet={packet_id} already claimed by {','.join(holders)} until {meta.get('claimed_until')}",
            file=sys.stderr,
        )
        return 1
    if claimed and holders == [login] and until and until > now:
        print(f"packet={packet_id} already claimed by {login}")
        print(f"issue={owner}/{repo}#{number}")
        return 0

    claimed_at = iso(now)
    claimed_until = iso(now + ttl)
    body = _set_body_keys(
        issue.get("body") or "",
        {
            "packet": packet_id,
            "ttl": meta.get("ttl") or "24h",
            "claimed_at": claimed_at,
            "claimed_until": claimed_until,
        },
    )
    new_labels = labels | {"packet", "claimed"}
    claim_type = (meta.get("claim_type") or "").strip()
    if claim_type in CLAIM_TYPES:
        new_labels.add(claim_type)
    prio = (meta.get("priority") or "").strip().upper()
    if prio in PRIORITY_RANK:
        new_labels.add(prio)
    new_labels = sorted(new_labels - {""})
    gh.update_issue(
        owner,
        repo,
        number,
        {
            "assignees": [login],
            "labels": new_labels,
            "body": body,
        },
    )
    print(f"packet={packet_id}")
    print(f"issue={owner}/{repo}#{number}")
    print(f"assignee={login}")
    print("label=claimed")
    print(f"claimed_until={claimed_until}")
    return 0
