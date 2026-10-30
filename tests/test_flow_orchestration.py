from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from factoria.application.artifacts import FlowArtifactStore
from factoria.application.flow_service import FlowService
from factoria.application.state_store import LocalFlowStateStore
from factoria.domain.flow import FlowState


class FlowOrchestrationTests(unittest.TestCase):
    def test_pause_and_resume_persist_flow_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            artifacts = FlowArtifactStore(project_root)
            state_store = LocalFlowStateStore(artifacts)
            service = FlowService(artifacts=artifacts, state_store=state_store)

            execution = service.create(flow_id="flow-1", kind="feature", label="OAuth")
            execution = service.start(execution)
            execution = service.pause(execution, reason="waiting for API contract")

            loaded = state_store.load("flow-1")
            self.assertEqual(loaded.flow.state, FlowState.PAUSED)
            self.assertEqual(loaded.label, "OAuth")
            self.assertEqual(loaded.flow.history[-1].reason, "waiting for API contract")

            resumed = service.resume(loaded)
            self.assertEqual(resumed.flow.state, FlowState.ACTIVE)

    def test_project_allows_only_one_incomplete_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            artifacts = FlowArtifactStore(project_root)
            state_store = LocalFlowStateStore(artifacts)
            service = FlowService(artifacts=artifacts, state_store=state_store)

            first = service.create(flow_id="flow-1", kind="fix")
            service.start(first)

            with self.assertRaises(RuntimeError):
                service.create(flow_id="flow-2", kind="feature")

    def test_completed_flow_cleans_temporary_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts = FlowArtifactStore(Path(temp_dir))
            state_store = LocalFlowStateStore(artifacts)
            service = FlowService(artifacts=artifacts, state_store=state_store)

            execution = service.start(service.create(flow_id="flow-1", kind="fix"))
            workspace = execution.workspace.root
            self.assertTrue(workspace.exists())

            completed = service.complete(execution)
            self.assertEqual(completed.flow.state, FlowState.COMPLETED)
            self.assertFalse(workspace.exists())


if __name__ == "__main__":
    unittest.main()
