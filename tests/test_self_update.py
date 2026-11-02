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
        self.move_tag_after_first_lookup = False
        self.tag_lookups = 0

    def __call__(self, command, **kwargs):
        command = tuple(str(item) for item in command)
        self.commands.append(command)
        if len(command) >= 4 and command[:2] == ("git", "-C"):
            args = command[3:]
            if args[:3] == ("remote", "get-url", "origin"):
                return self._done(command, "https://github.com/example/factoria.git\n")
            if args[:4] == ("fetch", "--quiet", "--no-tags", "origin"):
                return self._done(command)
            if args == ("rev-parse", "FETCH_HEAD^{commit}"):
                return self._done(command, "b" * 40 + "\n")
            if args == ("ls-remote", "--tags", "origin", "refs/tags/v*"):
                self.tag_lookups += 1
                target = "c" * 40 if self.move_tag_after_first_lookup and self.tag_lookups > 1 else "b" * 40
                # v0.3.0 is represented as an annotated tag; the peeled line is the commit.
                return self._done(
                    command,
                    "a" * 40 + "\trefs/tags/v0.2.0\n"
                    + "e" * 40 + "\trefs/tags/v0.3.0\n"
                    + target + "\trefs/tags/v0.3.0^{}\n",
                )
            if args[:2] == ("cat-file", "-e"):
                return self._done(command)
            if args[:2] == ("merge-base", "--is-ancestor"):
                return self._done(command)
            if args == ("rev-parse", "b" * 40 + "^{tree}"):
                return self._done(command, "d" * 40 + "\n")
            if args == ("show", "b" * 40 + ":pyproject.toml"):
                return self._done(command, '[project]\nname = "factoria"\nversion = "0.3.0"\n')
            if args == ("show", "b" * 40 + ":src/factoria/release.toml"):
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
        if len(command) >= 3 and command[1] == "-c":
            return self._done(
                command,
                "0.3.0\n" if not self.health_fail else "",
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
        (root / "pyproject.toml").write_text('[project]\nversion = "0.2.0"\n', encoding="utf-8")
        return root

    def _provenance(
        self,
        path: Path,
        *,
        sha: str = "a" * 40,
        version: str = "0.2.0",
        release_tag: str | None = None,
        tree_sha: str | None = None,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "version": version,
                    "commit_sha": sha,
                    "remote_url": "https://github.com/example/factoria.git",
                    "installed_at": "2026-11-01T00:00:00+00:00",
                    "release_tag": release_tag,
                    "tree_sha": tree_sha,
                }
            ),
            encoding="utf-8",
        )

    def _plan(self, service: UpdateService, root: Path, provenance: Path, *, tag: str | None = None):
        return service.inspect(
            root,
            remote="origin",
            branch="main",
            current_version=SemVer.parse("0.2.0"),
            provenance_path=provenance,
            release_tag=tag,
        )

    def test_inspect_selects_newest_remote_semver_tag_and_records_tree(self) -> None:
        runner = FakeRunner()
        service = UpdateService(runner=runner, python_executable="python")
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = self._checkout(base / "checkout")
            provenance = base / "installed.json"
            self._provenance(provenance)
            plan = self._plan(service, root, provenance)
        self.assertTrue(plan.available)
        self.assertTrue(plan.provenance_verified)
        self.assertEqual(plan.current_sha, "a" * 40)
        self.assertEqual(plan.release_tag, "v0.3.0")
        self.assertEqual(plan.target_sha, "b" * 40)
        self.assertEqual(plan.target_tree_sha, "d" * 40)
        self.assertEqual(plan.changes, ("bbbbbbbb Add update support",))

    def test_explicit_release_tag_can_be_selected_without_v_prefix(self) -> None:
        runner = FakeRunner()
        service = UpdateService(runner=runner, python_executable="python")
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = self._checkout(base / "checkout")
            provenance = base / "installed.json"
            self._provenance(provenance)
            plan = self._plan(service, root, provenance, tag="0.3.0")
        self.assertEqual(plan.release_tag, "v0.3.0")

    def test_update_without_exact_provenance_is_refused(self) -> None:
        runner = FakeRunner()
        service = UpdateService(runner=runner, python_executable="python")
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = self._checkout(base / "checkout")
            plan = self._plan(service, root, base / "missing.json")
            self.assertFalse(plan.provenance_verified)
            with self.assertRaises(UpdateError):
                service.apply(
                    plan,
                    state_path=base / "state.json",
                    config_path=base / "config.toml",
                    provenance_path=base / "installed.json",
                    confirmed=True,
                )

    def test_apply_refuses_if_remote_tag_moved_after_preview(self) -> None:
        runner = FakeRunner()
        service = UpdateService(runner=runner, python_executable="python")
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = self._checkout(base / "checkout")
            provenance = base / "installed.json"
            self._provenance(provenance)
            plan = self._plan(service, root, provenance)
            runner.move_tag_after_first_lookup = True
            runner.tag_lookups = 1
            with self.assertRaises(UpdateError):
                service.apply(
                    plan,
                    state_path=base / "state.json",
                    config_path=base / "config.toml",
                    provenance_path=provenance,
                    confirmed=True,
                )
        self.assertFalse(any("pip" in item and "install" in item for item in runner.commands))

    def test_apply_records_tag_tree_and_exact_rollback(self) -> None:
        runner = FakeRunner()
        service = UpdateService(runner=runner, python_executable="python")
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = self._checkout(base / "checkout")
            provenance = base / "installed.json"
            self._provenance(provenance, release_tag="v0.2.0")
            plan = self._plan(service, root, provenance)
            state = base / "state" / "previous.json"
            config = base / "config.toml"
            original = "# factoria: managed global config\ndefault_profile = \"normal\"\n"
            config.write_text(original, encoding="utf-8")
            result = service.apply(
                plan,
                state_path=state,
                config_path=config,
                provenance_path=provenance,
                confirmed=True,
            )
            self.assertTrue(result.health_ok)
            stored = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(stored["previous_sha"], "a" * 40)
            self.assertEqual(stored["target_tag"], "v0.3.0")
            self.assertEqual(stored["target_tree_sha"], "d" * 40)
            installed = json.loads(provenance.read_text(encoding="utf-8"))
            self.assertEqual(installed["commit_sha"], "b" * 40)
            self.assertEqual(installed["release_tag"], "v0.3.0")
            self.assertEqual(installed["tree_sha"], "d" * 40)
            config.write_text("changed\n", encoding="utf-8")
            rollback = service.rollback(
                state_path=state,
                config_path=config,
                provenance_path=provenance,
                confirmed=True,
            )
            self.assertTrue(rollback.health_ok)
            self.assertEqual(config.read_text(encoding="utf-8"), original)
            restored = json.loads(provenance.read_text(encoding="utf-8"))
            self.assertEqual(restored["commit_sha"], "a" * 40)
            self.assertEqual(restored["release_tag"], "v0.2.0")
            self.assertFalse(state.exists())

    def test_rollback_refuses_tree_integrity_mismatch(self) -> None:
        runner = FakeRunner()
        service = UpdateService(runner=runner, python_executable="python")
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            state = base / "previous.json"
            state.write_text(
                json.dumps(
                    {
                        "previous_version": "0.2.0",
                        "previous_sha": "a" * 40,
                        "target_version": "0.3.0",
                        "target_sha": "b" * 40,
                        "remote_url": "https://github.com/example/factoria.git",
                        "config_backup": None,
                        "created_at": "2026-11-02T00:00:00+00:00",
                        "previous_tag": "v0.2.0",
                        "previous_tree_sha": None,
                        "target_tag": "v0.3.0",
                        "target_tree_sha": "d" * 40,
                    }
                ),
                encoding="utf-8",
            )
            provenance = base / "installed.json"
            self._provenance(
                provenance,
                sha="b" * 40,
                version="0.3.0",
                release_tag="v0.3.0",
                tree_sha="f" * 40,
            )
            with self.assertRaises(UpdateError):
                service.rollback(
                    state_path=state,
                    config_path=base / "config.toml",
                    provenance_path=provenance,
                    confirmed=True,
                )

    def test_update_requires_confirmation(self) -> None:
        runner = FakeRunner()
        service = UpdateService(runner=runner, python_executable="python")
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = self._checkout(base / "checkout")
            provenance = base / "installed.json"
            self._provenance(provenance)
            plan = self._plan(service, root, provenance)
            with self.assertRaises(UpdateError):
                service.apply(
                    plan,
                    state_path=base / "state.json",
                    config_path=base / "config.toml",
                    provenance_path=provenance,
                    confirmed=False,
                )

    def test_failed_health_check_keeps_rollback_state(self) -> None:
        runner = FakeRunner()
        runner.health_fail = True
        service = UpdateService(runner=runner, python_executable="python")
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = self._checkout(base / "checkout")
            provenance = base / "installed.json"
            self._provenance(provenance)
            plan = self._plan(service, root, provenance)
            state = base / "state.json"
            result = service.apply(
                plan,
                state_path=state,
                config_path=base / "config.toml",
                provenance_path=provenance,
                confirmed=True,
            )
            self.assertFalse(result.health_ok)
            self.assertTrue(state.exists())


if __name__ == "__main__":
    unittest.main()
