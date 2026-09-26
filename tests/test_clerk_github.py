from __future__ import annotations

import unittest

from rc.clerk_github import apply_pending
from rc.http import HttpError


class Fake:
    def __init__(self, request: dict, repos: list[dict], beta: bool):
        self.request = request
        self.repos = repos
        self.beta = beta
        self.posts: list[dict] = []

    def __call__(self, method, path, payload):
        if method == "GET" and path.startswith(
            "/orgs/MagratheaLab/personal-access-token-requests?"
        ):
            return [self.request]
        if method == "GET" and path.endswith("/repositories?per_page=100"):
            return self.repos
        if "/teams/riemann-betatester-group01/memberships/" in path:
            if self.beta:
                return {"state": "active"}
            raise HttpError(404, path, "no")
        if "/teams/agents/memberships/" in path:
            raise HttpError(404, path, "no")
        if "/orgs/MagratheaLab/memberships/" in path:
            return {"state": "active", "role": "member"}
        if method == "POST" and "/personal-access-token-requests/" in path:
            self.posts.append(payload or {})
            return None
        raise AssertionError(f"unexpected {method} {path}")


def _beta_request():
    return {
        "id": 9,
        "owner": {"login": "ada"},
        "repository_selection": "subset",
        "permissions": {
            "repository": {
                "contents": "read",
                "issues": "write",
                "pull_requests": "read",
                "metadata": "read",
            }
        },
    }


class TestApplyPending(unittest.TestCase):
    def test_beta_member_is_approved(self):
        fake = Fake(
            _beta_request(),
            [{"name": "riemann"}, {"name": "riemann-reviews"}],
            beta=True,
        )
        lines = apply_pending(fake)
        self.assertEqual(fake.posts, [{"action": "approve", "reason": lines[0].split(" ", 3)[-1]}])
        self.assertIn("approve", lines[0])
        self.assertIn("user=ada", lines[0])

    def test_dry_run_does_not_post(self):
        fake = Fake(
            _beta_request(),
            [{"name": "riemann"}, {"name": "riemann-reviews"}],
            beta=True,
        )
        lines = apply_pending(fake, dry_run=True)
        self.assertEqual(fake.posts, [])
        self.assertIn("approve", lines[0])

    def test_stranger_reviewer_token_is_denied(self):
        fake = Fake(
            _beta_request(),
            [{"name": "riemann"}, {"name": "riemann-reviews"}],
            beta=False,
        )
        lines = apply_pending(fake)
        self.assertEqual(fake.posts[0]["action"], "deny")
        self.assertIn("deny", lines[0])
