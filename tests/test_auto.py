"""AUTO catalog (unit/shape). Live AUTO-1 needs a fixture packet + user W."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.support import FakeCore, FakeGitHub, SKILL, env_for, make_world, run_rc, serve


class TestAutoUnit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.world = make_world(Path(self.tmp.name))
        self.core_url, self.core = serve(FakeCore, skill=dict(SKILL))

    def tearDown(self):
        self.core.shutdown()
        self.tmp.cleanup()

    def test_auto2_empty_queue_prints_idle(self):
        url, httpd = serve(
            FakeGitHub, store={"issues": [], "comments": {}, "login": "tester"}
        )
        try:
            env = env_for(self.world, url, self.core_url)
            env["DISPATCHER_URL"] = "http://127.0.0.1:9"
            code, out, err = run_rc(["next"], env, self.world)
            self.assertEqual(code, 0, err)
            self.assertIn("packet=none", out)
            self.assertIn("IDLE", out)
        finally:
            httpd.shutdown()
