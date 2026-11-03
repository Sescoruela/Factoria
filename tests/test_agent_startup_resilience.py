from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from factoria.adapters.codex_discovery import discover_codex
from factoria.adapters.opencode import _opencode_timeout_seconds
from factoria.web_app import _JOBS, _JOBS_LOCK, _job, _start_async_job


class CodexDiscoveryTests(unittest.TestCase):
    def test_explicit_codex_cli_path_wins(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            executable = Path(temp) / "codex.exe"
            executable.write_bytes(b"")
            with patch.dict(os.environ, {"CODEX_CLI_PATH": str(executable)}, clear=False):
                result = discover_codex()
            self.assertEqual(result.cli_path, executable.resolve())
            self.assertEqual(result.cli_source, "CODEX_CLI_PATH")

    def test_desktop_detection_does_not_claim_cli_without_runtime_binary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            local = Path(temp)
            (local / "OpenAI" / "Codex").mkdir(parents=True)
            env = {"LOCALAPPDATA": str(local), "PATH": "", "CODEX_CLI_PATH": ""}
            with patch("factoria.adapters.codex_discovery.sys.platform", "win32"), patch.dict(
                os.environ, env, clear=False
            ), patch("factoria.adapters.codex_discovery.shutil.which", return_value=None):
                result = discover_codex()
            self.assertTrue(result.desktop_detected)
            self.assertIsNone(result.cli_path)
            self.assertIsNone(result.cli_source)

    def test_desktop_runtime_binary_is_discovered_after_explicit_and_path_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            local = Path(temp)
            executable = local / "OpenAI" / "Codex" / "bin" / "codex.exe"
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"")
            env = {"LOCALAPPDATA": str(local), "PATH": "", "CODEX_CLI_PATH": ""}
            with patch("factoria.adapters.codex_discovery.sys.platform", "win32"), patch.dict(
                os.environ, env, clear=False
            ), patch("factoria.adapters.codex_discovery.shutil.which", return_value=None):
                result = discover_codex()
            self.assertEqual(result.cli_path, executable.resolve())
            self.assertEqual(result.cli_source, "ChatGPT Desktop runtime")
            self.assertTrue(result.desktop_detected)


class OpenCodeTimeoutTests(unittest.TestCase):
    def test_default_timeout_is_bounded(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_opencode_timeout_seconds(1800), 600)
            self.assertEqual(_opencode_timeout_seconds(120), 120)

    def test_timeout_override_is_bounded(self) -> None:
        with patch.dict(os.environ, {"FACTORIA_OPENCODE_TIMEOUT_SECONDS": "90"}, clear=False):
            self.assertEqual(_opencode_timeout_seconds(1800), 90)
        with patch.dict(os.environ, {"FACTORIA_OPENCODE_TIMEOUT_SECONDS": "99999"}, clear=False):
            self.assertEqual(_opencode_timeout_seconds(1800), 1800)


class WebAgentJobTests(unittest.TestCase):
    def setUp(self) -> None:
        with _JOBS_LOCK:
            _JOBS.clear()

    def tearDown(self) -> None:
        with _JOBS_LOCK:
            _JOBS.clear()

    def test_agent_job_returns_immediately_and_finishes_in_background(self) -> None:
        def fake_run(args, project):
            time.sleep(0.05)
            return 0, "ok"

        with patch("factoria.web_app._run_factoria_command", side_effect=fake_run):
            job = _start_async_job(["feature", "demo"], None)
            self.assertIn(job["status"], {"queued", "running"})
            deadline = time.time() + 2
            current = None
            while time.time() < deadline:
                current = _job(str(job["id"]))
                if current and current["status"] == "completed":
                    break
                time.sleep(0.02)
            self.assertIsNotNone(current)
            self.assertEqual(current["status"], "completed")
            self.assertEqual(current["output"], "ok")

    def test_second_agent_job_for_same_project_is_rejected(self) -> None:
        gate = False

        def fake_run(args, project):
            nonlocal gate
            deadline = time.time() + 1
            while not gate and time.time() < deadline:
                time.sleep(0.01)
            return 0, "done"

        project = Path("demo")
        with patch("factoria.web_app._run_factoria_command", side_effect=fake_run):
            _start_async_job(["fix", "one"], project)
            with self.assertRaises(ValueError):
                _start_async_job(["feature", "two"], project)
            gate = True


if __name__ == "__main__":
    unittest.main()
