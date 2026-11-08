from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from factoria.adapters.codex_discovery import discover_codex
from factoria.adapters.opencode import _opencode_timeout_seconds
from factoria.application.tool_presence import tool_presence
from factoria.web_app import _JOBS, _JOBS_LOCK, _job, _start_async_job


class CodexDiscoveryTests(unittest.TestCase):
    def test_store_chatgpt_is_visible_without_cli_or_starting_processes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "Packages" / "OpenAI.ChatGPT-Desktop_fixture"
            package.mkdir(parents=True)
            env = {"LOCALAPPDATA": temp, "CODEX_CLI_PATH": ""}
            with patch("factoria.adapters.codex_discovery.sys.platform", "win32"), patch.dict(
                os.environ, env
            ), patch("factoria.adapters.codex_discovery.shutil.which", return_value=None), patch(
                "subprocess.run", side_effect=AssertionError("No processes during discovery")
            ):
                result = tool_presence()[0]
            self.assertTrue(result["desktop_detected"])
            self.assertEqual(result["desktop_hint"], str(package))
            self.assertFalse(result["available"])
            self.assertFalse(result["cli_available"])
            self.assertFalse(result["ready"])

    def test_package_name_must_be_a_directory_and_match_openai(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            packages = Path(temp) / "Packages"
            packages.mkdir()
            (packages / "OpenAI.ChatGPT_fake_file").write_text("")
            (packages / "Other.ChatGPT_fixture").mkdir()
            with patch("factoria.adapters.codex_discovery.sys.platform", "win32"), patch.dict(
                os.environ, {"LOCALAPPDATA": temp, "CODEX_CLI_PATH": ""}
            ), patch("factoria.adapters.codex_discovery.shutil.which", return_value=None):
                self.assertFalse(discover_codex().desktop_detected)

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

    def test_agent_launch_requests_are_rejected_without_starting_worker(self) -> None:
        with patch('factoria.web_app.threading.Thread') as thread:
            for command in ('feature', 'fix', 'resume'):
                with self.subTest(command=command), self.assertRaisesRegex(ValueError, 'fuera'):
                    _start_async_job([command, 'demo'], None)
            thread.assert_not_called()
        self.assertFalse(_JOBS)

    def test_rejected_launch_creates_no_background_job(self) -> None:
        with self.assertRaises(ValueError):
            _start_async_job(['fix', 'one'], Path('demo'))
        self.assertIsNone(_job('missing'))


if __name__ == "__main__":
    unittest.main()
