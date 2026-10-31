from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from factoria.cli import build_parser, main


class CliTests(unittest.TestCase):
    def test_parser_exposes_expected_commands(self) -> None:
        parser = build_parser()
        for command in (
            "memoria-init",
            "memoria-update",
            "fix",
            "feature",
            "status",
            "resume",
            "pause",
            "cancel",
            "plugins",
        ):
            with self.subTest(command=command):
                namespace = parser.parse_args([command] + (["example"] if command in {"fix", "feature", "pause", "cancel"} else []))
                self.assertEqual(namespace.command, command)

    def test_status_reports_uninitialized_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--project", temp_dir, "status"])
            self.assertEqual(code, 0)
            self.assertIn("Memoria: no inicializada", output.getvalue())
            self.assertIn("Flujos activos: ninguno", output.getvalue())

    def test_read_only_blocks_fix_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            error = io.StringIO()
            with redirect_stderr(error):
                code = main(["--project", temp_dir, "--read-only", "fix", "Bug"])
            self.assertEqual(code, 1)
            self.assertIn("read-only", error.getvalue())
            self.assertFalse((Path(temp_dir) / ".factoria" / "work").exists())

    def test_cancel_requires_explicit_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--project", temp_dir, "cancel", "missing-flow"])
            self.assertEqual(code, 2)
            self.assertIn("--yes", output.getvalue())

    def test_plugins_without_roots_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--project", temp_dir, "plugins"])
            self.assertEqual(code, 0)
            self.assertIn("No plugins discovered", output.getvalue())


if __name__ == "__main__":
    unittest.main()
