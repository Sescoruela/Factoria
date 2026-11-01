from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from factoria.application.self_update import UpdateError, UpdateService
from factoria.versioning import SemVer, VersionError


class SemVerTests(unittest.TestCase):
    def test_semver_orders_release_after_prerelease(self) -> None:
        self.assertLess(SemVer.parse("1.2.3-rc.1"), SemVer.parse("1.2.3"))
        self.assertLess(SemVer.parse("1.2.3"), SemVer.parse("1.3.0"))

    def test_build_metadata_does_not_change_precedence(self) -> None:
        self.assertEqual(SemVer.parse("1.2.3+one"), SemVer.parse("1.2.3+two"))

    def test_invalid_semver_is_rejected(self) -> None:
        with self.assertRaises(VersionError):
            SemVer.parse("1.2")


class FakeRunner:
    def __init__(self) -> None:
        self.commands: list[tuple[str, ...]] = []
        self.install_fail = False
        self.health_fail = False

    def __call__(self, command, **kwargs):
        command = tuple(str(item) for item in command)
        self.commands.append(command)
        if len(command) >= 4 and command[:2] == ("git", "-C"):
            args = command[3:]
            if args[:4] == ("fetch", "--quiet", "--no-tags", "origin"):
                return self._done(command)
            if args == ("rev-parse", "FETCH_HEAD"):
                return self._done(command, "b" * 40 + "\n")
            if args == ("rev-parse", "HEAD"):
                return self._done(command, "a" * 40 + "\n")
            if args == ("remote", "get-url", "origin"):
                return self._done(command, "https://github.com/example/factoria.git\n")
            if args == ("show", "FETCH_HEAD:pyproject.toml"):
                return self._done(command, '[project]\nname = "factoria"\nversion = "0.3.0"\n')
            if args == ("show", "FETCH_HEAD:src/factoria/release.toml"):
                return self._done(
                    command,
                    'version = "0.3.0"\nnotes = ["new updater"]\nmemory_changes = []\nconfig_changes = []\n',
                )
            if args[:3] == ("log", "--format=%h %s", "--max-count=20"):
                return self._done(command, "bbbbbbbb Add update support\n")
        if "pip" in command and "install" in command:
            return self._done(
                command,
                "",
                "install failed" if self.install_fail else "",
                1 if self.install_fail else 0,
            )
        if command[1:3] == (
            "-c",
            "from factoria.entrypoint import build_update_parser; build_update_parser()",
        ):
            return self._done(
                command,
                "",
                "health failed" if self.health_fail else "",
                1 if self.health_fail else 0,
            )
        raise AssertionError(f"Unexpected command: {command}")

    @staticmethod
    def _done(command, stdout="", stderr="", returncode=0):
        return subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr=stderr)


class UpdateServiceTests(unittest.TestCase):
    def _checkout(self, root: Path) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        (root / ".git").mkdir()
        (root / "pyproject.toml").write_text(
            '[project]\nversion = "0.2.0"\n', encoding="utf-8"
        )
        return root

    def test_inspect_builds_semver_update_plan(self) -> None:
        runner = FakeRunner()
        service = UpdateService(runner=runner, python_executable="python")
        with tempfile.TemporaryDirectory() as tmp:
            root = self._checkout(Path(tmp) / "checkout")
            plan = service.inspect(
                root,
                remote="origin",
                branch="main",
                current_version=SemVer.parse("0.2.0"),
            )
        self.assertTrue(plan.available)
        self.assertEqual(str(plan.target_version), "0.3.0")
        self.assertEqual(plan.changes, ("bbbbbbbb Add update support",))
        self.assertEqual(plan.release.notes, ("new updater",))

    def test_apply_records_rollback_and_restores_managed_config(self) -> None:
        runner = FakeRunner()
        service = UpdateService(runner=runner, python_executable="python")
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = self._checkout(base / "checkout")
            plan = service.inspect(
                root,
                remote="origin",
                branch="main",
                current_version=SemVer.parse("0.2.0"),
            )
            state = base / "state" / "previous.json"
            config = base / "config.toml"
            original = "# factoria: managed global config\ndefault_profile = \"normal\"\n"
            config.write_text(original, encoding="utf-8")
            result = service.apply(plan, state_path=state, config_path=config, confirmed=True)
            self.assertTrue(result.health_ok)
            stored = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(stored["previous_version"], "0.2.0")
            config.write_text("changed\n", encoding="utf-8")
            rollback = service.rollback(state_path=state, config_path=config, confirmed=True)
            self.assertTrue(rollback.health_ok)
            self.assertEqual(config.read_text(encoding="utf-8"), original)
            self.assertFalse(state.exists())

    def test_update_requires_confirmation(self) -> None:
        runner = FakeRunner()
        service = UpdateService(runner=runner, python_executable="python")
        with tempfile.TemporaryDirectory() as tmp:
            root = self._checkout(Path(tmp) / "checkout")
            plan = service.inspect(
                root,
                remote="origin",
                branch="main",
                current_version=SemVer.parse("0.2.0"),
            )
            with self.assertRaises(UpdateError):
                service.apply(
                    plan,
                    state_path=Path(tmp) / "state.json",
                    config_path=Path(tmp) / "config.toml",
                    confirmed=False,
                )

    def test_failed_health_check_keeps_rollback_state(self) -> None:
        runner = FakeRunner()
        runner.health_fail = True
        service = UpdateService(runner=runner, python_executable="python")
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = self._checkout(base / "checkout")
            plan = service.inspect(
                root,
                remote="origin",
                branch="main",
                current_version=SemVer.parse("0.2.0"),
            )
            state = base / "state.json"
            result = service.apply(
                plan,
                state_path=state,
                config_path=base / "config.toml",
                confirmed=True,
            )
            self.assertFalse(result.health_ok)
            self.assertTrue(state.exists())


if __name__ == "__main__":
    unittest.main()
