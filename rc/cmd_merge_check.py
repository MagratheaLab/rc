"""Owner-assistant: GO/NO-GO card. Never merges."""

from __future__ import annotations

import json
import re
import sys
from rc.config import Config
from rc.delivery import word_count
from rc.github_api import GitHub, split_repo
from rc.linter import lint_lean_source

REVIEW_BLOCK = re.compile(
    r"MAGRATHEA_REVIEW\s+"
    r"family:\s*(?P<family>\S+)\s+"
    r"adversary:\s*(?P<adversary>true|false)\s+"
    r"verdict:\s*(?P<verdict>accept|reject)",
    re.I,
)


def _line(name: str, value: str) -> str:
    return f"{name:<20} {value}"


def parse_reviews(comments: list[dict]) -> list[dict]:
    out = []
    for comment in comments:
        match = REVIEW_BLOCK.search(comment.get("body") or "")
        if not match:
            continue
        out.append(
            {
                "family": match.group("family"),
                "adversary": match.group("adversary").lower() == "true",
                "verdict": match.group("verdict").lower(),
            }
        )
    return out


def gate_status(check_runs: list[dict]) -> str:
    gates = [c for c in check_runs if (c.get("name") or "") == "gate"]
    if not gates:
        return "MISSING"
    last = gates[-1]
    conc = (last.get("conclusion") or "").lower()
    if conc == "success":
        return "PASS"
    return "FAIL"


def evaluate(
    *,
    pr: dict,
    files: list[dict],
    check_runs: list[dict],
    comments: list[dict],
    file_contents: dict[str, str],
) -> dict[str, str]:
    sha = (pr.get("head") or {}).get("sha") or ""
    names = [f.get("filename") or "" for f in files]
    cert_raw = file_contents.get("CERTIFICATE.json")
    summary_raw = file_contents.get("SUMMARY.md")

    cert_st = "MISSING"
    stmt_st = "MISSING"
    packet = None
    allowed: list[str] = []
    if cert_raw:
        try:
            cert = json.loads(cert_raw)
            cert_st = "PASS" if cert.get("packet") and cert.get("claim_type") else "FAIL"
            packet = cert.get("packet")
            allowed = list(cert.get("allowed_files") or [])
            stmt_st = "PASS" if cert.get("statement_hash") else "FAIL"
        except json.JSONDecodeError:
            cert_st = "FAIL"

    if not summary_raw:
        summary_st = "MISSING"
        words = 0
    else:
        words = word_count(summary_raw)
        summary_st = "FAIL" if words > 500 else "PASS"

    extra_ok = {"CERTIFICATE.json", "SUMMARY.md"}
    if packet:
        extra_ok.add(f"packets/{packet}.md")
    allowed_st = "PASS"
    for name in names:
        if name not in allowed and name not in extra_ok:
            allowed_st = "FAIL"
            break

    sorry = "CLEAN"
    for name, src in file_contents.items():
        if name.endswith(".lean"):
            errs = lint_lean_source(src)
            if errs:
                sorry = "HIT"
                break
        patch = ""
        for f in files:
            if f.get("filename") == name:
                patch = f.get("patch") or ""
        if re.search(r"\b(sorry|admit|native_decide|unsafe)\b", patch):
            sorry = "HIT"

    reviews = [r for r in parse_reviews(comments) if r["verdict"] == "accept"]
    families = sorted({r["family"] for r in reviews})
    nfam = len(families)
    has_adv = any(r["adversary"] for r in reviews)
    if nfam >= 3 and has_adv:
        adv_st = "PASS"
        fam_st = f"{nfam}/3  list={','.join(families)}"
    else:
        adv_st = "PASS" if has_adv else "MISSING"
        fam_st = f"{nfam}/3  list={','.join(families) or '-'}"

    gate_st = gate_status(check_runs)
    blockers = []
    if gate_st != "PASS":
        blockers.append("GATE")
    if nfam < 3:
        blockers.append("FAMILIES")
    if adv_st != "PASS":
        blockers.append("ADVERSARY")
    if cert_st != "PASS":
        blockers.append("CERTIFICATE")
    if summary_st != "PASS":
        blockers.append("SUMMARY")
    if stmt_st != "PASS":
        blockers.append("STATEMENT_HASH")
    if sorry != "CLEAN":
        blockers.append("SORRY_OR_REWRITE")
    if allowed_st != "PASS":
        blockers.append("ALLOWED_FILES")

    verdict = "GO" if not blockers else "NO-GO"
    return {
        "pr": str(pr.get("number") or ""),
        "sha": sha[:12],
        "GATE": gate_st,
        "FAMILIES": fam_st,
        "ADVERSARY": adv_st,
        "CERTIFICATE": cert_st,
        "SUMMARY": f"{summary_st}   words={words}",
        "STATEMENT_HASH": stmt_st,
        "SORRY_OR_REWRITE": sorry,
        "ALLOWED_FILES": allowed_st,
        "VERDICT": verdict,
        "BLOCKERS": ",".join(blockers) or "-",
    }


def render(card: dict[str, str]) -> str:
    lines = [
        f"MERGE_CHECK pr={card['pr']} sha={card['sha']}",
        _line("GATE", card["GATE"]),
        _line("FAMILIES", card["FAMILIES"]),
        _line("ADVERSARY", card["ADVERSARY"]),
        _line("CERTIFICATE", card["CERTIFICATE"]),
        _line("SUMMARY", card["SUMMARY"]),
        _line("STATEMENT_HASH", card["STATEMENT_HASH"]),
        _line("SORRY_OR_REWRITE", card["SORRY_OR_REWRITE"]),
        _line("ALLOWED_FILES", card["ALLOWED_FILES"]),
        _line("VERDICT", card["VERDICT"]),
        _line("BLOCKERS", card["BLOCKERS"]),
    ]
    return "\n".join(lines) + "\n"


def _contents_from_files(files: list[dict]) -> dict[str, str]:
    out = {}
    for f in files:
        name = f.get("filename") or ""
        patch = f.get("patch") or ""
        # Reconstruct added files from patch when GitHub sends it.
        if f.get("raw"):
            out[name] = f["raw"]
            continue
        body = []
        for line in patch.splitlines():
            if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
                continue
            if line.startswith("+"):
                body.append(line[1:])
            elif line.startswith("-"):
                continue
            elif line.startswith("\\"):
                continue
            else:
                body.append(line[1:] if line.startswith(" ") else line)
        if body:
            out[name] = "\n".join(body) + "\n"
    return out


def run(cfg: Config, argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: rc merge-check owner/repo <pr>", file=sys.stderr)
        return 2
    repo_s, pr_s = argv[0], argv[1]
    if not cfg.token:
        print("GH_TOKEN required (read-only is enough; merge-check never merges)", file=sys.stderr)
        return 1
    owner, repo = split_repo(repo_s)
    gh = GitHub(cfg.github_api, cfg.token)
    pr = gh.get(f"/repos/{owner}/{repo}/pulls/{pr_s}")
    files = gh.get(f"/repos/{owner}/{repo}/pulls/{pr_s}/files?per_page=100")
    if not isinstance(files, list):
        files = []
    sha = (pr.get("head") or {}).get("sha") or ""
    checks = gh.get(f"/repos/{owner}/{repo}/commits/{sha}/check-runs")
    check_runs = checks.get("check_runs") if isinstance(checks, dict) else []
    comments = gh.comments(owner, repo, int(pr_s))
    contents = _contents_from_files(files)
    # Prefer raw file API for cert/summary if present.
    for name in ("CERTIFICATE.json", "SUMMARY.md"):
        if name in [f.get("filename") for f in files] and name not in contents:
            try:
                meta = gh.get(f"/repos/{owner}/{repo}/contents/{name}?ref={sha}")
                if isinstance(meta, dict) and meta.get("encoding") == "base64":
                    import base64

                    contents[name] = base64.b64decode(meta["content"]).decode()
            except Exception:
                pass
    card = evaluate(
        pr=pr,
        files=files,
        check_runs=check_runs or [],
        comments=comments,
        file_contents=contents,
    )
    print(render(card), end="")
    print("merged=no")
    return 0 if card["VERDICT"] == "GO" else 1
