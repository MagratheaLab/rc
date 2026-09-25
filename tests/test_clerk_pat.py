from __future__ import annotations

import unittest

from rc.clerk_pat import decide


def _ok(**overrides):
    req = {
        "repository_selection": "subset",
        "repositories": [{"name": "riemann"}],
        "permissions": {
            "contents": "write",
            "issues": "write",
            "pull_requests": "write",
            "metadata": "read",
        },
    }
    req.update(overrides)
    return req


class TestClerkPat(unittest.TestCase):
    def test_approve_riemann_only(self):
        decision, reason = decide(_ok())
        self.assertEqual(decision, "approve")
        self.assertIn("riemann", reason)

    def test_deny_ops(self):
        decision, _ = decide(_ok(repositories=[{"name": "ops"}]))
        self.assertEqual(decision, "deny")

    def test_deny_extra_repo(self):
        decision, _ = decide(
            _ok(repositories=[{"name": "riemann"}, {"name": "reviews"}])
        )
        self.assertEqual(decision, "deny")

    def test_deny_admin_permission(self):
        req = _ok()
        req["permissions"]["administration"] = "write"
        decision, reason = decide(req)
        self.assertEqual(decision, "deny")
        self.assertIn("administration", reason)

    def test_deny_all_repos(self):
        decision, reason = decide(_ok(repository_selection="all"))
        self.assertEqual(decision, "deny")
        self.assertIn("all", reason)
