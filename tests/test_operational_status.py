from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from factoria.application.status import OperationalStatusService, _memory_version_warning
from factoria.domain.models import CheckResult
from factoria.adapters.base import ToolCapability
from factoria.entrypoint import _primary_command


class FakeAdapter:
    name = "fake"
    executable = "fake"

    def capabilities(self):
        return frozenset({ToolCapability.NON_INTERACTIVE, ToolCapability.PROJECT_DIRECTORY})

    def available(self) -> bool:
        return True

    def self_test(self):
        raise AssertionError("status must remain lightweight and not run adapter self-tests")

    def build_command(self, request):
        raise NotImplementedError

    def run(self, request):
        raise NotImplementedError


def git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


class OperationalStatusTests(unittest.TestCase):
    def init_repo(self, root: Path) -> None:
        git(root, "init", "-b", "main")
        git(root, "config", "user.email", "tests@example.invalid")
        git(root, "config", "user.name", "Factoria Tests")
        (root / "README.md").write_text("demo\n", encoding="utf-8")
        git(root, "add", "README.md")
        git(root, "commit", "-m", "initial")

    def test_status_is_lightweight_and_reports_missing_memory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as home_dir:
            root = Path(temp_dir)
            home = Path(home_dir)
            self.init_repo(root)
            config = home / ".factoria" / "config.toml"
            config.parent.mkdir(parents=True)
            config.write_text('default_profile = "normal"\ndefault_tool = "fake"\n', encoding="utf-8")

            with patch("pathlib.Path.home", return_value=home):
                report = OperationalStatusService(adapters=(FakeAdapter(),)).inspect(root)

            self.assertFalse(report.memory_initialized)
            self.assertEqual(report.effective_tool, "fake")
            self.assertEqual(report.tools[0].name, "fake")
            self.assertTrue(any("memoria-init" in item for item in report.recommendations))

    def test_status_blocks_on_secret_like_material_in_changed_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as home_dir:
            root = Path(temp_dir)
            home = Path(home_dir)
            self.init_repo(root)
            (home / ".factoria").mkdir(parents=True)
            (home / ".factoria" / "config.toml").write_text(
                'default_profile = "normal"\ndefault_tool = "fake"\n',
                encoding="utf-8",
            )
            (root / "local.env").write_text(
                'api_key = "abcdefghijklmnopqrstuvwx"\n',
                encoding="utf-8",
            )

            with patch("pathlib.Path.home", return_value=home):
                report = OperationalStatusService(adapters=(FakeAdapter(),)).inspect(root)

            self.assertTrue(report.dirty)
            self.assertTrue(report.security.blocked)
            self.assertEqual(report.security.finding_count, 1)
            self.assertNotIn("abcdefghijklmnopqrstuvwx", "\n".join(report.security.summaries))
            self.assertTrue(any("Security gate" in item for item in report.warnings))

    def test_patch_memory_version_difference_does_not_warn(self) -> None:
        with patch("factoria.application.status._installed_version", return_value="0.2.9"):
            self.assertIsNone(_memory_version_warning("0.2.0"))

    def test_minor_memory_version_difference_warns(self) -> None:
        with patch("factoria.application.status._installed_version", return_value="0.3.0"):
            warning = _memory_version_warning("0.2.9")
        self.assertIsNotNone(warning)
        self.assertIn("minor version differs", warning)

    def test_entrypoint_finds_status_after_global_project_option(self) -> None:
        self.assertEqual(
            _primary_command(["--project", "/tmp/demo", "status", "--all"]),
            "status",
        )


if __name__ == "__main__":
    unittest.main()
