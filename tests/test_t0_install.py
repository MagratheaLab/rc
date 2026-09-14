"""T0 Install — TEST_PLAN.md"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from tests.support import (
    FakeCore,
    FakeGitHub,
    SKILL,
    env_for,
    issue,
    make_world,
    run_rc,
    serve,
)


class TestT0Install(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.world = make_world(self.root)
        self.core_url, self.core = serve(FakeCore, skill=dict(SKILL))
        self.gh_url, self.gh = serve(
            FakeGitHub, store={"issues": [issue()], "comments": {}, "login": "tester"}
        )

    def tearDown(self):
        self.core.shutdown()
        self.gh.shutdown()
        self.tmp.cleanup()

    def test_doctor_fails_if_skill_version_missing(self):
        url, srv = serve(FakeCore, skill={"name": "magrathea"})
        try:
            env = env_for(self.world, self.gh_url, url)
            code, _out, err = run_rc(["doctor"], env, self.world)
            self.assertEqual(code, 1)
            self.assertIn("skill tag missing", err)
        finally:
            srv.shutdown()

    def test_doctor_fails_if_gate_image_unpinned(self):
        env = env_for(self.world, self.gh_url, self.core_url, extra={"RC_GATE_IMAGE": "magrathea-gate:latest"})
        code, _out, err = run_rc(["doctor"], env, self.world)
        self.assertEqual(code, 1)
        self.assertIn("gate image unpinned", err)

    def test_doctor_ok_when_skill_and_digest_present(self):
        env = env_for(self.world, self.gh_url, self.core_url)
        code, out, err = run_rc(["doctor"], env, self.world)
        self.assertEqual(code, 0, err)
        self.assertIn("DOCTOR_OK", out)
        self.assertIn("moltbook=not_used", out)
        self.assertIn("dispatcher_localhost=not_used", out)

    def test_next_requires_github_token_not_moltbook(self):
        env = env_for(self.world, self.gh_url, self.core_url, extra={"GH_TOKEN": "", "RC_GITHUB_TOKEN": ""})
        env.pop("GH_TOKEN", None)
        env.pop("RC_GITHUB_TOKEN", None)
        env.pop("GITHUB_TOKEN", None)
        code, _out, err = run_rc(["next"], env, self.world)
        self.assertEqual(code, 1)
        self.assertIn("GH_TOKEN", err)

    def test_next_lists_fixture_packet_without_hermes_app(self):
        env = env_for(self.world, self.gh_url, self.core_url)
        code, out, err = run_rc(["next"], env, self.world)
        self.assertEqual(code, 0, err)
        self.assertIn("packet=P-20260914-fx01", out)
        self.assertIn("priority=P2", out)
        urls = FakeGitHub.store.get("urls", [])
        self.assertTrue(any("/issues" in u for u in urls))
        self.assertFalse(any("moltbook" in u.lower() for u in urls))
        self.assertFalse(any("dispatcher" in u.lower() for u in urls))

    def test_default_github_api_is_not_localhost(self):
        from rc.config import DEFAULT_GITHUB_API

        self.assertEqual(DEFAULT_GITHUB_API, "https://api.github.com")

    def test_unimplemented_sprint2_commands_exit_2(self):
        env = env_for(self.world, self.gh_url, self.core_url)
        for cmd in ("rate", "heartbeat"):
            code, _out, err = run_rc([cmd], env, self.world)
            self.assertEqual(code, 2, cmd)
            self.assertIn("RC_NOT_IMPLEMENTED", err)
