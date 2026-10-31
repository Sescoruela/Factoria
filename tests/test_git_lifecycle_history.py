from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from factoria.application.artifacts import FlowArtifactStore
from factoria.application.flow_service import FlowService
from factoria.application.git_lifecycle import GitLifecycle, GitLifecycleError
from factoria.application.history import LocalExecutionHistoryStore
from factoria.application.state_store import LocalFlowStateStore


def git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def init_repo(root: Path) -> None:
    git(root, "init", "-b", "main")
    git(root, "config", "user.email", "factoria@example.invalid")
    git(root, "config", "user.name", "Factoria Tests")
    (root / "README.md").write_text("# Test\n", encoding="utf-8")
    git(root, "add", "README.md")
    git(root, "commit", "-m", "Initial")


class GitLifecycleTests(unittest.TestCase):
    def test_preview_then_confirmed_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            git(root, "switch", "-c", "fix/example")
            artifacts = FlowArtifactStore(root)
            store = LocalFlowStateStore(artifacts)
            service = FlowService(artifacts=artifacts, state_store=store)
            execution = service.start(service.create(flow_id="flow-1", kind="fix", label="repair parser"))
            (root / "README.md").write_text("# Fixed\n", encoding="utf-8")

            lifecycle = GitLifecycle(root)
            proposal = lifecycle.prepare(execution)
            self.assertEqual(proposal.branch, "fix/example")
            self.assertEqual(proposal.message, "fix: repair parser")
            self.assertEqual(tuple(item.path for item in proposal.changes), ("README.md",))

            result = lifecycle.commit(proposal, confirmed=True)
            self.assertEqual(result.message, "fix: repair parser")
            self.assertEqual(lifecycle.changes(), ())
            self.assertEqual(result.sha, git(root, "rev-parse", "HEAD"))

    def test_commit_on_main_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            artifacts = FlowArtifactStore(root)
            service = FlowService(artifacts=artifacts)
            execution = service.start(service.create(flow_id="flow-2", kind="feature", label="new thing"))
            (root / "README.md").write_text("changed\n", encoding="utf-8")
            with self.assertRaises(GitLifecycleError):
                GitLifecycle(root).prepare(execution)


class HistoryTests(unittest.TestCase):
    def test_history_is_stored_inside_git_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            artifacts = FlowArtifactStore(root)
            store = LocalFlowStateStore(artifacts)
            service = FlowService(artifacts=artifacts, state_store=store)
            execution = service.start(service.create(flow_id="flow-3", kind="fix", label="history"))
            artifacts.write_text("flow-3", "task.md", "task\n")
            history = LocalExecutionHistoryStore(root)
            snapshot = history.snapshot(execution.workspace.root)
            cancelled = service.cancel(execution, reason="test")
            record = history.archive(
                cancelled,
                artifacts=snapshot,
                branch="fix/history",
                commit_sha=git(root, "rev-parse", "HEAD"),
            )

            self.assertEqual(record.state, "cancelled")
            self.assertIn("task.md", record.artifacts)
            self.assertIn(".git", str(history.history_root()))
            self.assertFalse(execution.workspace.root.exists())
            self.assertEqual(history.list()[0].flow_id, "flow-3")


if __name__ == "__main__":
    unittest.main()
