"""Blind review submit. Store is MagratheaLab/reviews until quorum."""

from __future__ import annotations

import argparse
import sys

from rc.cmd_merge_check import parse_reviews
from rc.config import Config
from rc.github_api import GitHub, split_repo

DEFAULT_REVIEW_REPO = "MagratheaLab/reviews"


def _block(packet: str, family: str, adversary: bool, verdict: str) -> str:
    return (
        f"MAGRATHEA_REVIEW\n"
        f"family: {family}\n"
        f"adversary: {'true' if adversary else 'false'}\n"
        f"verdict: {verdict}\n"
        f"packet: {packet}\n"
    )


def _quorum(reviews: list[dict]) -> bool:
    accepts = [r for r in reviews if r["verdict"] == "accept"]
    families = {r["family"] for r in accepts}
    return len(families) >= 3 and any(r["adversary"] for r in accepts)


def run(cfg: Config, argv: list[str]) -> int:
    if not argv or argv[0] in {"-h", "--help"}:
        print("usage: rc review submit P-... --pr N --family X --verdict accept|reject [--adversary]")
        print("       rc review inbox P-...")
        return 2
    sub = argv[0]
    if sub == "inbox":
        return inbox(cfg, argv[1:])
    if sub != "submit":
        print(f"unknown review subcommand: {sub}", file=sys.stderr)
        return 2
    return submit(cfg, argv[1:])


def submit(cfg: Config, argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="rc review submit")
    p.add_argument("packet")
    p.add_argument("--pr", type=int, required=True)
    p.add_argument("--family", required=True)
    p.add_argument("--verdict", choices=["accept", "reject"], required=True)
    p.add_argument("--adversary", action="store_true")
    p.add_argument("--world-repo", default=cfg.repo or "MagratheaLab/riemann")
    args = p.parse_args(argv)
    if not cfg.token:
        print("GH_TOKEN required", file=sys.stderr)
        return 1
    review_repo = __import__("os").environ.get("RC_REVIEW_REPO") or DEFAULT_REVIEW_REPO
    gh = GitHub(cfg.github_api, cfg.token)
    ro, rr = split_repo(review_repo)
    wo, wr = split_repo(args.world_repo)
    body = _block(args.packet, args.family, args.adversary, args.verdict)
    issue = gh.create_issue(
        ro,
        rr,
        title=f"{args.packet} family={args.family}",
        body=body,
        labels=["pending", "packet", args.packet],
    )
    print(f"stored={ro}/{rr}#{issue.get('number')} pending=yes published=no")

    pending = gh.list_issues(ro, rr, labels=f"pending,{args.packet}")
    reviews = parse_reviews(pending)
    if not _quorum(reviews):
        print("quorum=no")
        return 0
    for item in pending:
        gh.create_comment(wo, wr, args.pr, item.get("body") or "")
        labels = []
        for lab in item.get("labels") or []:
            name = lab.get("name") if isinstance(lab, dict) else str(lab)
            if name and name != "pending":
                labels.append(name)
        labels.append("published")
        gh.update_issue(ro, rr, item["number"], {"labels": labels, "state": "closed"})
    print("quorum=yes published=yes")
    return 0


def inbox(cfg: Config, argv: list[str]) -> int:
    if not argv:
        print("usage: rc review inbox P-...", file=sys.stderr)
        return 2
    packet = argv[0]
    if not cfg.token:
        print("GH_TOKEN required", file=sys.stderr)
        return 1
    review_repo = __import__("os").environ.get("RC_REVIEW_REPO") or DEFAULT_REVIEW_REPO
    gh = GitHub(cfg.github_api, cfg.token)
    ro, rr = split_repo(review_repo)
    items = gh.list_issues(ro, rr, labels=f"pending,{packet}")
    print(f"pending={len(items)} packet={packet} (bodies hidden until quorum)")
    return 0
