"""T3 Gates — TEST_PLAN.md (linters always; docker lake when daemon exists)."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from rc.cmd_gate import _docker_run_ref
from tests.support import (
    FakeCore,
    LEAN_NOTATION,
    LEAN_REWRITE,
    LEAN_SORRY,
    SKILL,
    env_for,
    make_world,
    run_rc,
    serve,
)


def _docker() -> bool:
    try:
        subprocess.run(
            ["docker", "info"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=8,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


class TestT3Gates(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.world = make_world(self.root)  # clean rfl on main
        self.core_url, self.core = serve(FakeCore, skill=dict(SKILL))
        self.addCleanup(self.core.shutdown)
        self.env = env_for(self.world, "http://127.0.0.1:9", self.core_url)
        code, _out, err = run_rc(["work", "P-20260914-fx01"], self.env, self.world)
        self.assertEqual(code, 0, err)
        self.lean = (
            self.world / ".rc" / "work" / "P-20260914-fx01" / "RiemannCanon.lean"
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_ci_lake_mode_passes_linters_without_docker(self):
        env = dict(self.env)
        env["RC_LAKE_MODE"] = "ci"
        code, out, err = run_rc(["gate", "P-20260914-fx01"], env, self.world)
        self.assertEqual(code, 0, err + out)
        self.assertIn("lake=ci", out)
        self.assertIn("gate=pass", out)

    def test_delivery_flag_rejects_lake_mode_ci(self):
        env = dict(self.env)
        env["RC_LAKE_MODE"] = "ci"
        code, _out, err = run_rc(["gate", "--ci", "P-20260914-fx01"], env, self.world)
        self.assertEqual(code, 1)
        self.assertIn("RC_LAKE_MODE=ci", err)

    def test_sorry_fails_gate(self):
        self.lean.write_text(LEAN_SORRY, encoding="utf-8")
        code, _out, err = run_rc(["gate", "P-20260914-fx01"], self.env, self.world)
        self.assertEqual(code, 1)
        self.assertIn("sorry", err.lower())

    def test_header_rewrite_fails_gate(self):
        self.lean.write_text(LEAN_REWRITE, encoding="utf-8")
        code, _out, err = run_rc(["gate", "P-20260914-fx01"], self.env, self.world)
        self.assertEqual(code, 1)
        self.assertIn("header rewrite", err)

    def test_local_notation_fails_gate(self):
        self.lean.write_text(LEAN_NOTATION, encoding="utf-8")
        code, _out, err = run_rc(["gate", "P-20260914-fx01"], self.env, self.world)
        self.assertEqual(code, 1)
        self.assertIn("local notation", err)

    def test_bit_identical_gate_hash_for_same_source(self):
        self.lean.write_text(LEAN_SORRY, encoding="utf-8")
        c1, out1, _e1 = run_rc(["gate", "P-20260914-fx01"], self.env, self.world)
        c2, out2, _e2 = run_rc(["gate", "P-20260914-fx01"], self.env, self.world)
        self.assertEqual(c1, 1)
        self.assertEqual(c2, 1)
        h1 = [ln for ln in out1.splitlines() if ln.startswith("gate_hash=")]
        h2 = [ln for ln in out2.splitlines() if ln.startswith("gate_hash=")]
        self.assertEqual(h1, h2)
        self.assertTrue(h1[0].startswith("gate_hash=sha256:"))
        digest = h1[0].split("=", 1)[1]
        self.assertEqual(len(digest), len("sha256:") + 64)

    def test_github_actions_env_does_not_require_certificate(self):
        self.lean.write_text(LEAN_SORRY, encoding="utf-8")
        env = dict(self.env)
        env["GITHUB_ACTIONS"] = "true"
        code, _out, err = run_rc(["gate", "P-20260914-fx01"], env, self.world)
        self.assertEqual(code, 1)
        self.assertIn("sorry", err.lower())
        self.assertNotIn("CERTIFICATE.json", err)

    def test_docker_run_ref_uses_image_id_not_name_at_digest(self):
        image_id = "sha256:" + ("c" * 64)
        self.assertEqual(
            _docker_run_ref(f"magrathea-gate:lean-4.33.0@{image_id}"),
            image_id,
        )
        self.assertEqual(_docker_run_ref("magrathea-gate:lean-4.33.0"), "magrathea-gate:lean-4.33.0")
        pinned = "ghcr.io/magrathealab/gate:lean-4.33.0@sha256:" + ("b" * 64)
        self.assertEqual(_docker_run_ref(pinned), pinned)

    def test_docker_copy_does_not_preserve_ownership(self):
        src = Path(__file__).resolve().parents[1] / "rc" / "cmd_gate.py"
        text = src.read_text(encoding="utf-8")
        self.assertIn("cp -R --no-preserve=ownership", text)
        self.assertIn("bash", text)
        self.assertNotIn('"-lc"', text)


@unittest.skipUnless(_docker(), "docker daemon not running on this host")
class TestDockerLake(unittest.TestCase):
    def test_clean_fixture_lake_build(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            world = make_world(Path(tmp.name))
            core_url, core = serve(FakeCore, skill=dict(SKILL))
            repo = Path(__file__).resolve().parents[1]
            subprocess.run(
                ["docker", "build", "-t", "magrathea-gate:lean-4.33.0", str(repo / "gate")],
                check=True,
            )
            inspect = subprocess.run(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{.Id}}",
                    "magrathea-gate:lean-4.33.0",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            image_id = inspect.stdout.strip()
            env = env_for(world, "http://127.0.0.1:9", core_url)
            env["RC_GATE_IMAGE"] = f"magrathea-gate:lean-4.33.0@{image_id}"
            run_rc(["work", "P-20260914-fx01"], env, world)
            code, out, err = run_rc(["gate", "P-20260914-fx01"], env, world)
            self.assertEqual(code, 0, err + out)
            self.assertIn("gate=pass", out)
            core.shutdown()
        finally:
            tmp.cleanup()
