from __future__ import annotations

import json
import os
import subprocess
import threading
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from rc.cli import main as rc_main

PINNED_IMAGE = (
    "magrathea-gate:lean-4.33.0@"
    "sha256:" + ("a" * 64)
)

LEAN_OK = """/-
  Fixture island only. Not a step toward RH.
  Declaration name is frozen for packet P-20260914-fx01.
-/

theorem one_add_one : 1 + 1 = 2 := rfl
"""

LEAN_SORRY = """theorem one_add_one : 1 + 1 = 2 := sorry
"""

LEAN_REWRITE = """theorem one_add_one : 1 + 1 = 3 := rfl
"""

LEAN_NOTATION = """local notation "⊤" => True
theorem one_add_one : 1 + 1 = 2 := rfl
"""

PACKET = """---
id: P-20260914-fx01
parent: null
goal: Build the frozen declaration RiemannCanon.one_add_one.
allowed_files:
  - RiemannCanon.lean
forbidden: any other file; moltbook threads; mathlib
max_context_tokens: 8000
local_gates:
  - lake build RiemannCanon
success:
  - CERTIFICATE.json valid
  - SUMMARY.md <= 500 words
  - lake build succeeds for RiemannCanon.one_add_one
review_families_required: 3
adversary_required: true
claim_types_allowed: [lemma]
claim_type: lemma
canon_hash: REPLACE
skill_version: 0.1.4
lean_declaration: RiemannCanon.one_add_one
priority: P2
ttl: 24h
---

## Notes for the worker

Fixture packet. Do not touch the theorem header.
"""

CANON = """# CANON (frozen identifiers)

- `claim_type` values — `lemma | numeric | blocked | adversary`
"""

ISSUE_BODY = """packet: P-20260914-fx01
priority: P2
claim_type: lemma
ttl: 24h
family:
lean_declaration: RiemannCanon.one_add_one
skill_version: 0.1.4

Fixture only. Not RH.
File: packets/P-20260914-fx01.md
"""

SKILL = {"name": "magrathea", "version": "0.1.4", "files": ["SKILL.md"]}


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def make_world(root: Path, *, lean: str = LEAN_OK) -> Path:
    world = root / "world"
    world.mkdir()
    (world / "packets").mkdir()
    (world / "defs").mkdir()
    (world / "RiemannCanon.lean").write_text(lean, encoding="utf-8")
    (world / "packets" / "P-20260914-fx01.md").write_text(PACKET, encoding="utf-8")
    (world / "defs" / "CANON.md").write_text(CANON, encoding="utf-8")
    (world / "lakefile.toml").write_text(
        'name = "riemann"\ndefaultTargets = ["RiemannCanon"]\n\n[[lean_lib]]\nname = "RiemannCanon"\n',
        encoding="utf-8",
    )
    (world / "lean-toolchain").write_text("leanprover/lean4:v4.33.0\n", encoding="utf-8")
    (world / "lake-manifest.json").write_text(
        '{"version":"1.1.0","packagesDir":".lake/packages","packages":[],"name":"riemann","lakeDir":".lake"}\n',
        encoding="utf-8",
    )
    (world / "SECRET.md").write_text("should not appear in rc work\n", encoding="utf-8")
    git(world, "init")
    git(world, "config", "user.email", "rc@test")
    git(world, "config", "user.name", "rc")
    git(world, "add", ".")
    git(world, "commit", "-m", "fx01")
    git(world, "branch", "-M", "main")
    return world


class FakeCore(BaseHTTPRequestHandler):
    skill = SKILL

    def log_message(self, *_args):
        return

    def do_GET(self):
        if self.path.endswith("skill.json") or self.path == "/skill.json":
            body = json.dumps(self.skill).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()


class FakeGitHub(BaseHTTPRequestHandler):
    store: dict

    def log_message(self, *_args):
        return

    def _json(self, code: int, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        return json.loads(self.rfile.read(n).decode())

    def do_GET(self):
        self.store.setdefault("urls", []).append("GET " + self.path)
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/user":
            return self._json(200, {"login": self.store.get("login", "tester")})
        if "/check-runs" in path:
            return self._json(200, {"check_runs": self.store.get("check_runs") or []})
        if "/pulls/" in path and path.endswith("/files"):
            number = int(path.split("/pulls/")[1].split("/")[0])
            return self._json(200, self.store.get("pr_files", {}).get(number, []))
        if "/pulls/" in path:
            number = int(path.rstrip("/").split("/")[-1])
            pr = (self.store.get("pulls") or {}).get(number)
            if not pr:
                return self._json(404, {"message": "not found"})
            return self._json(200, pr)
        if path.endswith("/issues") or "/issues?" in self.path:
            qs = parse_qs(parsed.query)
            want = [x for x in qs.get("labels", [""])[0].split(",") if x]
            items = []
            for issue in self.store["issues"]:
                names = {l["name"] for l in issue["labels"]}
                if want and not set(want).issubset(names):
                    continue
                if issue.get("state") != "open":
                    continue
                items.append(issue)
            return self._json(200, items)
        if "/comments" in path:
            number = int(path.split("/issues/")[1].split("/")[0])
            return self._json(200, self.store.get("comments", {}).get(number, []))
        if "/issues/" in path:
            number = int(path.rstrip("/").split("/")[-1])
            for issue in self.store["issues"]:
                if issue["number"] == number:
                    return self._json(200, issue)
            return self._json(404, {"message": "not found"})
        return self._json(404, {"message": self.path})

    def do_PATCH(self):
        self.store.setdefault("urls", []).append("PATCH " + self.path)
        number = int(self.path.rstrip("/").split("/")[-1])
        payload = self._read()
        for issue in self.store["issues"]:
            if issue["number"] != number:
                continue
            if "body" in payload:
                issue["body"] = payload["body"]
            if "labels" in payload:
                issue["labels"] = [{"name": n} for n in payload["labels"]]
            if "assignees" in payload:
                issue["assignees"] = [{"login": n} for n in payload["assignees"]]
                issue["assignee"] = issue["assignees"][0] if issue["assignees"] else None
            return self._json(200, issue)
        return self._json(404, {"message": "not found"})

    def do_PUT(self):
        self.store.setdefault("urls", []).append("PUT " + self.path)
        return self._json(403, {"message": "merge-check must not merge"})

    def do_POST(self):
        self.store.setdefault("urls", []).append("POST " + self.path)
        if "/merge" in self.path:
            return self._json(403, {"message": "merge-check must not merge"})
        payload = self._read()
        if self.path.rstrip("/").endswith("/comments"):
            number = int(self.path.split("/issues/")[1].split("/")[0])
            comments = self.store.setdefault("comments", {}).setdefault(number, [])
            comments.append({"body": payload.get("body") or ""})
            return self._json(201, comments[-1])
        if self.path.endswith("/issues"):
            issues = self.store.setdefault("issues", [])
            number = max([i.get("number") or 0 for i in issues], default=0) + 1
            labels = [{"name": n} for n in (payload.get("labels") or [])]
            issue = {
                "number": number,
                "title": payload.get("title") or "",
                "body": payload.get("body") or "",
                "state": "open",
                "labels": labels,
                "assignees": [],
                "assignee": None,
            }
            issues.append(issue)
            return self._json(201, issue)
        if self.path.endswith("/pulls"):
            pr = {"number": 1, "html_url": "https://github.com/example/world/pull/1", **payload}
            self.store.setdefault("prs", []).append(pr)
            return self._json(201, pr)
        return self._json(404, {"message": self.path})


def serve(handler, **ns) -> tuple[str, ThreadingHTTPServer]:
    for key, val in ns.items():
        setattr(handler, key, val)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address
    return f"http://127.0.0.1:{port}", httpd


def issue(body: str = ISSUE_BODY, **extra) -> dict:
    data = {
        "number": 1,
        "title": "P-20260914-fx01 fixture Lean island",
        "state": "open",
        "body": body,
        "labels": [{"name": "packet"}],
        "assignees": [],
        "assignee": None,
    }
    data.update(extra)
    return data


def env_for(world: Path, github: str, core: str, extra: dict | None = None) -> dict:
    env = os.environ.copy()
    env.update(
        {
            "RC_WORLD": str(world),
            "RC_REPO": "MagratheaLab/riemann",
            "RC_GITHUB_API": github,
            "RC_GITHUB_TOKEN": "test-token",
            "GH_TOKEN": "test-token",
            "RC_CORE_SKILL_URL": core.rstrip("/") + "/published-skills/skill.json",
            "RC_GATE_IMAGE": PINNED_IMAGE,
            "RC_FAMILY": "A",
            "RC_AGENT_ID": "tester",
            "RC_MODEL_ID": "test-model",
        }
    )
    if extra:
        env.update(extra)
    return env


def run_rc(args: list[str], env: dict, cwd: Path) -> tuple[int, str, str]:
    import io
    from contextlib import redirect_stderr, redirect_stdout

    old = os.environ.copy()
    os.environ.clear()
    os.environ.update(env)
    out, err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            code = rc_main(args)
    finally:
        os.environ.clear()
        os.environ.update(old)
    return code, out.getvalue(), err.getvalue()
