from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from factoria.application.artifacts import FlowArtifactStore
from factoria.application.final_report import parse_agent_metrics, render_final_report
from factoria.application.flow_service import FlowService
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


class FinalReportTests(unittest.TestCase):
    def test_agent_metrics_use_only_persisted_evidence(self) -> None:
        metrics = parse_agent_metrics(
            "step=implement role=implementer attempt=1 adapter=codex profile=potente "
            "model=model-a fallback=false passed=true\n"
            "step=review role=reviewer attempt=1 adapter=opencode profile=potente "
            "model=model-b fallback=true passed=true metrics_source=real "
            "input_tokens=120 output_tokens=30 cost_usd=0.012\n"
        )
        self.assertEqual(metrics.attempts, 2)
        self.assertEqual(metrics.fallback_attempts, 1)
        self.assertEqual(metrics.adapters, ("codex", "opencode"))
        self.assertEqual(metrics.models, ("model-a", "model-b"))
        self.assertEqual(metrics.usage_source, "real")
        self.assertEqual(metrics.input_tokens, 120)
        self.assertEqual(metrics.output_tokens, 30)
        self.assertAlmostEqual(metrics.cost_usd or 0, 0.012)

    def test_missing_usage_is_not_estimated(self) -> None:
        metrics = parse_agent_metrics(
            "step=implement role=implementer attempt=1 adapter=codex profile=potente "
            "model=model-a fallback=false passed=true\n"
        )
        self.assertEqual(metrics.usage_source, "unavailable")
        self.assertIsNone(metrics.input_tokens)
        self.assertIsNone(metrics.cost_usd)

    def test_report_contains_stable_sections_and_transition_history(self) -> None:
        record = SimpleNamespace(
            flow_id="flow-1",
            kind="fix",
            state="completed",
            label="repair parser",
            branch="fix/parser",
            commit_sha="abc123",
            duration_seconds=12.5,
            permission_profile="normal",
            permission_escalated=False,
            transitions=(
                {
                    "source": "created",
                    "target": "active",
                    "occurred_at": "2026-01-01T00:00:00+00:00",
                    "reason": None,
                },
                {
                    "source": "active",
                    "target": "completed",
                    "occurred_at": "2026-01-01T00:00:12+00:00",
                    "reason": None,
                },
            ),
            artifacts={
                "task.md": "# Fix\n\nRepair parser\n",
                "verification.md": "# Verification\n\n- PASS unit-tests\n",
                "review.md": "# Review\n\n- result: approved\n",
                "agents.log": (
                    "step=implement role=implementer attempt=1 adapter=codex profile=potente "
                    "model=model-a fallback=false passed=true\n"
                ),
                "commit.json": json.dumps(
                    {"message": "fix: repair parser", "files": ["parser.py"]}
                ),
            },
        )
        report = render_final_report(record)
        for heading in (
            "Summary",
            "Changes",
            "Verification",
            "Review",
            "Security",
            "Permissions",
            "Agent metrics",
            "Recommendation",
            "State history",
        ):
            self.assertIn(heading, report)
        self.assertIn("parser.py", report)
        self.assertIn("usage_source: unavailable", report)
        self.assertIn("not estimated", report)
        self.assertIn("created -> active", report)


class HistoryMetricTests(unittest.TestCase):
    def test_archive_persists_metrics_transitions_and_full_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            artifacts = FlowArtifactStore(root)
            store = LocalFlowStateStore(artifacts)
            service = FlowService(artifacts=artifacts, state_store=store)
            execution = service.start(
                service.create(flow_id="flow-history", kind="fix", label="metrics")
            )
            artifacts.write_text("flow-history", "task.md", "# Fix\n\nDo thing\n")
            artifacts.write_text(
                "flow-history",
                "agents.log",
                "step=implement role=implementer attempt=1 adapter=codex profile=potente "
                "model=model-x fallback=false passed=true\n",
            )
            history = LocalExecutionHistoryStore(root)
            snapshot = history.snapshot(execution.workspace.root)
            cancelled = service.cancel(execution, reason="test cancel")
            record = history.archive(
                cancelled,
                artifacts=snapshot,
                branch="fix/metrics",
                commit_sha=git(root, "rev-parse", "HEAD"),
            )

            self.assertEqual(record.agent_attempts, 1)
            self.assertEqual(record.agent_adapters, ("codex",))
            self.assertGreaterEqual(len(record.transitions), 2)
            report_path = history.history_root() / "flow-history.txt"
            report = report_path.read_text(encoding="utf-8")
            self.assertIn("FACTORIA FINAL REPORT", report)
            self.assertIn("State history", report)
            self.assertIn("test cancel", report)


if __name__ == "__main__":
    unittest.main()
