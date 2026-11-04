from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from factoria.ui_app import ManagedTerminalUI
from factoria.ui_workspace import UiWorkspaceSettings, discover_projects, project_root
from factoria.web_app import _save_selected_project, _selected_project


class ProjectDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name).resolve()
        self.project = self.workspace / "application"
        (self.project / ".git").mkdir(parents=True)
        self.child = self.project / "packages" / "frontend"
        (self.child / ".git").mkdir(parents=True)
        self.source = self.child / "src"
        self.source.mkdir()

    def test_nested_repositories_are_one_project_but_siblings_remain(self) -> None:
        sibling = self.workspace / "group" / "other"
        (sibling / ".git").mkdir(parents=True)
        self.assertEqual(set(discover_projects(self.workspace)), {self.project, sibling})

    def test_scan_at_repository_or_subfolder_returns_owning_root(self) -> None:
        self.assertEqual(discover_projects(self.project), (self.project,))
        self.assertEqual(discover_projects(self.project / "packages"), (self.project,))

    def test_selection_normalizes_nested_repository_with_workspace_boundary(self) -> None:
        self.assertEqual(project_root(self.source, self.workspace), self.project)
        self.assertEqual(project_root(self.source, self.child), self.child)
        self.assertEqual(discover_projects(self.child), (self.child,))
        self.assertIsNone(project_root(self.workspace / "missing", self.workspace))

    def test_arbitrary_or_dangling_git_files_are_not_projects(self) -> None:
        for index, content in enumerate(("not a git repository", "gitdir: missing", "gitdir:", "\udcff")):
            folder = self.workspace / f"invalid-{index}"
            folder.mkdir()
            (folder / ".git").write_bytes(content.encode("utf-8", errors="surrogateescape"))
        self.assertEqual(discover_projects(self.workspace), (self.project,))

    def test_real_external_worktree_remains_independent(self) -> None:
        repo = self.workspace / "real"
        repo.mkdir()
        def git(*args: str) -> None:
            subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
        git("init")
        git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "--allow-empty", "-m", "initial")
        worktree = self.workspace / "real-worktree"
        git("worktree", "add", "-b", "worktree-test", str(worktree))
        self.assertTrue((worktree / ".git").is_file())
        self.assertEqual(set(discover_projects(self.workspace)), {self.project, repo, worktree})

    def test_web_selection_and_saved_subfolder_use_main_project(self) -> None:
        with patch("pathlib.Path.home", return_value=self.workspace):
            UiWorkspaceSettings(self.workspace, self.source).save()
            self.assertEqual(_selected_project(UiWorkspaceSettings.load()), self.project)
            _save_selected_project(self.source)
            self.assertEqual(UiWorkspaceSettings.load().last_project, self.project)
            with self.assertRaises(ValueError):
                _save_selected_project(self.workspace / "missing")
            self.assertEqual(UiWorkspaceSettings.load().last_project, self.project)

    def test_terminal_repairs_saved_nested_selection(self) -> None:
        with patch("pathlib.Path.home", return_value=self.workspace):
            UiWorkspaceSettings(self.workspace, self.source).save()
            ui = ManagedTerminalUI(self.workspace, output_fn=lambda _text: None)
            ui._ensure_project_context()
            self.assertEqual(ui.root, self.project)
            self.assertEqual(UiWorkspaceSettings.load().last_project, self.project)

    def test_terminal_search_when_workspace_is_inside_repository(self) -> None:
        folder = self.project / "packages"
        answers = iter(["/application", "1"])
        with patch("pathlib.Path.home", return_value=self.workspace):
            UiWorkspaceSettings(folder, None).save()
            ui = ManagedTerminalUI(folder, input_fn=lambda _prompt: next(answers), output_fn=lambda _text: None)
            ui._select_project(interactive=True)
            self.assertEqual(ui.root, self.project)
            self.assertEqual(UiWorkspaceSettings.load().last_project, self.project)
