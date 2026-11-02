from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from factoria.application.artifacts import FlowWorkspace
from factoria.application.flow_service import FlowExecution
from factoria.application.runtime_state import (
    LiveFlowSession,
    RuntimeStage,
    RuntimeStateError,
    load_live_session,
    save_live_session,
    validate_runtime_state,
)
from factoria.domain.flow import Flow, FlowState


class RuntimeStateUnificationTests(unittest.TestCase):
    def _execution(self, state: FlowState, *, kind: str = "feature") -> FlowExecution:
        workspace = FlowWorkspace(flow_id="flow-1", root=Path("/tmp/factoria-flow-1"))
        return FlowExecution(
            flow=Flow(flow_id="flow-1", kind=kind, state=state),
            workspace=workspace,
            label="demo",
        )

    def _session(self, stage: RuntimeStage | None) -> LiveFlowSession:
        return LiveFlowSession(
            flow_id="flow-1",
            kind="feature",
            title="demo",
            branch="feature/demo",
            preferred_tool="codex",
            runtime_stage=stage,
        )

    def test_active_requires_running_stage(self) -> None:
        execution = self._execution(FlowState.ACTIVE)
        validate_runtime_state(execution, self._session(RuntimeStage.RUNNING))
        with self.assertRaises(RuntimeStateError):
            validate_runtime_state(
                execution,
                self._session(RuntimeStage.AWAITING_PLAN_APPROVAL),
            )

    def test_paused_requires_a_pause_stage(self) -> None:
        execution = self._execution(FlowState.PAUSED)
        validate_runtime_state(
            execution,
            self._session(RuntimeStage.AWAITING_PLAN_APPROVAL),
        )
        validate_runtime_state(
            execution,
            self._session(RuntimeStage.AWAITING_FINAL_APPROVAL),
        )
        validate_runtime_state(
            execution,
            self._session(RuntimeStage.READY_FOR_COMMIT),
        )
        with self.assertRaises(RuntimeStateError):
            validate_runtime_state(execution, self._session(RuntimeStage.RUNNING))

    def test_blocked_state_is_canonical_and_has_no_runtime_stage(self) -> None:
        execution = self._execution(FlowState.BLOCKED)
        validate_runtime_state(execution, self._session(None))
        with self.assertRaises(RuntimeStateError):
            validate_runtime_state(execution, self._session(RuntimeStage.RUNNING))

    def test_legacy_phase_is_read_but_not_written(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "agent-flow.json"
            path.write_text(
                json.dumps(
                    {
                        "flow_id": "flow-1",
                        "kind": "feature",
                        "title": "demo",
                        "branch": "feature/demo",
                        "preferred_tool": "codex",
                        "phase": "awaiting_plan_approval",
                        "large_fix": False,
                        "update_memory": False,
                        "base_permission_profile": "normal",
                        "permission_profile": "normal",
                        "permission_escalated": False,
                    }
                ),
                encoding="utf-8",
            )
            execution = self._execution(FlowState.PAUSED)
            session = load_live_session(path, execution=execution)
            self.assertIs(session.runtime_stage, RuntimeStage.AWAITING_PLAN_APPROVAL)

            save_live_session(path, session)
            persisted = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["runtime_stage"], "awaiting_plan_approval")
            self.assertNotIn("phase", persisted)

    def test_legacy_blocked_phase_cannot_override_flow_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "agent-flow.json"
            payload = {
                "flow_id": "flow-1",
                "kind": "feature",
                "title": "demo",
                "branch": "feature/demo",
                "preferred_tool": None,
                "phase": "blocked",
                "large_fix": False,
                "update_memory": False,
                "base_permission_profile": "normal",
                "permission_profile": "normal",
                "permission_escalated": False,
            }
            path.write_text(json.dumps(payload), encoding="utf-8")

            blocked = load_live_session(path, execution=self._execution(FlowState.BLOCKED))
            self.assertIsNone(blocked.runtime_stage)

            with self.assertRaises(RuntimeStateError):
                load_live_session(path, execution=self._execution(FlowState.PAUSED))

    def test_terminal_state_rejects_runtime_progress(self) -> None:
        execution = self._execution(FlowState.COMPLETED)
        with self.assertRaises(RuntimeStateError):
            validate_runtime_state(execution, self._session(RuntimeStage.READY_FOR_COMMIT))


if __name__ == "__main__":
    unittest.main()
