from __future__ import annotations

import unittest
from datetime import UTC, datetime

from factoria.domain.flow import Flow, FlowState, FlowStateMachine, InvalidTransitionError


class FlowStateMachineTests(unittest.TestCase):
    def test_flow_uses_explicit_valid_transitions(self) -> None:
        flow = Flow(flow_id="flow-1", kind="feature")
        started = flow.transition(FlowState.ACTIVE, occurred_at=datetime(2026, 10, 30, tzinfo=UTC))
        paused = started.transition(FlowState.PAUSED)
        resumed = paused.transition(FlowState.ACTIVE)
        completed = resumed.transition(FlowState.COMPLETED)

        self.assertEqual(flow.state, FlowState.CREATED)
        self.assertEqual(completed.state, FlowState.COMPLETED)
        self.assertEqual(len(completed.history), 4)

    def test_terminal_states_cannot_transition(self) -> None:
        flow = Flow(flow_id="flow-1", kind="fix").transition(FlowState.CANCELLED)
        with self.assertRaises(InvalidTransitionError):
            flow.transition(FlowState.ACTIVE)

    def test_plugin_extension_cannot_add_outgoing_transition_to_terminal_state(self) -> None:
        machine = FlowStateMachine.default()
        with self.assertRaises(InvalidTransitionError):
            machine.extend([(FlowState.COMPLETED, FlowState.ACTIVE)])


if __name__ == "__main__":
    unittest.main()
