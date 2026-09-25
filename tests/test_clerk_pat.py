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

    def test_nested_github_permissions_still_approve_worker(self):
        decision, reason = decide(
            _ok(
                permissions={
                    "repository": {
                        "contents": "write",
                        "issues": "write",
                        "pull_requests": "write",
                        "metadata": "read",
                    },
                    "organization": {},
                    "other": {},
                }
            )
        )
        self.assertEqual(decision, "approve")
        self.assertIn("riemann", reason)

    def test_deny_org_permission(self):
        decision, reason = decide(
            _ok(permissions={"organization": {"members": "read"}, "repository": {}})
        )
        self.assertEqual(decision, "deny")
        self.assertIn("org", reason)

    def _beta(self, **overrides):
        req = {
            "repository_selection": "subset",
            "repositories": [{"name": "reviews"}, {"name": "riemann"}],
            "permissions": {
                "repository": {
                    "contents": "read",
                    "issues": "write",
                    "pull_requests": "read",
                    "metadata": "read",
                }
            },
            "teams": ["riemann-betatester-group01"],
            "org_role": "member",
        }
        req.update(overrides)
        return req

    def test_approve_beta_reviewer(self):
        decision, reason = decide(self._beta())
        self.assertEqual(decision, "approve")
        self.assertIn("beta reviewer", reason)

    def test_beta_without_team_denied(self):
        decision, reason = decide(self._beta(teams=[]))
        self.assertEqual(decision, "deny")
        self.assertIn("riemann-betatester-group01", reason)

    def test_beta_member_cannot_take_worker_token(self):
        decision, reason = decide(_ok(teams=["riemann-betatester-group01"]))
        self.assertEqual(decision, "deny")
        self.assertIn("not a worker", reason)

    def test_deny_owner(self):
        decision, reason = decide(_ok(org_role="admin"))
        self.assertEqual(decision, "deny")
        self.assertEqual(reason, "owner")
