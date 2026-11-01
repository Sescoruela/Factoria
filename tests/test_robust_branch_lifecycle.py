from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from factoria.application.branch_lifecycle import BranchLifecycleError, GitBranchLifecycle
from factoria.robust_lifecycle_cli import build_parser


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


class BranchLifecycleTests(unittest.TestCase):
    def _repo(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        git(root, "init", "-b", "main")
        git(root, "config", "user.email", "factoria@example.invalid")
        git(root, "config", "user.name", "Factoria Tests")
        (root / "README.md").write_text("base\n", encoding="utf-8")
        git(root, "add", "README.md")
        git(root, "commit", "-m", "base")
        return temp, root

    def test_unique_commits_are_reported(self) -> None:
        temp, root = self._repo()
        try:
            git(root, "switch", "-c", "factoria/work")
            (root / "feature.txt").write_text("change\n", encoding="utf-8")
            git(root, "add", "feature.txt")
            git(root, "commit", "-m", "unique work")

            inspection = GitBranchLifecycle(root).inspect("factoria/work")
            self.assertEqual(len(inspection.unique_commits), 1)
            self.assertEqual(inspection.unique_commits[0].subject, "unique work")
        finally:
            temp.cleanup()

    def test_unique_branch_cannot_be_deleted_without_backup(self) -> None:
        temp, root = self._repo()
        try:
            git(root, "switch", "-c", "factoria/work")
            (root / "feature.txt").write_text("change\n", encoding="utf-8")
            git(root, "add", "feature.txt")
            git(root, "commit", "-m", "unique work")

            with self.assertRaises(BranchLifecycleError):
                GitBranchLifecycle(root).delete_branch("factoria/work")
            self.assertTrue(GitBranchLifecycle(root).branch_exists("factoria/work"))
        finally:
            temp.cleanup()

    def test_backup_is_created_before_unique_branch_deletion(self) -> None:
        temp, root = self._repo()
        try:
            git(root, "switch", "-c", "factoria/work")
            (root / "feature.txt").write_text("change\n", encoding="utf-8")
            git(root, "add", "feature.txt")
            git(root, "commit", "-m", "unique work")

            manager = GitBranchLifecycle(root)
            manager.delete_branch("factoria/work", backup_name="backup/factoria-work")

            self.assertFalse(manager.branch_exists("factoria/work"))
            self.assertTrue(manager.branch_exists("backup/factoria-work"))
            self.assertEqual(git(root, "branch", "--show-current"), "main")
        finally:
            temp.cleanup()

    def test_branch_switch_refuses_dirty_worktree(self) -> None:
        temp, root = self._repo()
        try:
            git(root, "branch", "factoria/work")
            (root / "README.md").write_text("dirty\n", encoding="utf-8")
            with self.assertRaises(BranchLifecycleError):
                GitBranchLifecycle(root).switch_to_flow_branch("factoria/work")
        finally:
            temp.cleanup()


class RobustLifecycleParserTests(unittest.TestCase):
    def test_cancel_requires_separate_branch_confirmation_flags(self) -> None:
        args = build_parser().parse_args(
            [
                "cancel",
                "flow-1",
                "--yes",
                "--delete-branch",
                "--confirm-delete-branch",
                "--backup-branch",
                "backup/flow-1",
            ]
        )
        self.assertTrue(args.yes)
        self.assertTrue(args.delete_branch)
        self.assertTrue(args.confirm_delete_branch)
        self.assertEqual(args.backup_branch, "backup/flow-1")

    def test_resume_supports_explicit_branch_switch(self) -> None:
        args = build_parser().parse_args(["resume", "flow-1", "--switch-branch"])
        self.assertTrue(args.switch_branch)


if __name__ == "__main__":
    unittest.main()
