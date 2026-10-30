from datetime import UTC, datetime

import pytest

from factoria.domain.flow import Flow, FlowState, FlowStateMachine, InvalidTransitionError


def test_flow_uses_explicit_valid_transitions() -> None:
    flow = Flow(flow_id="flow-1", kind="feature")
    started = flow.transition(FlowState.ACTIVE, occurred_at=datetime(2026, 10, 30, tzinfo=UTC))
    paused = started.transition(FlowState.PAUSED)
    resumed = paused.transition(FlowState.ACTIVE)
    completed = resumed.transition(FlowState.COMPLETED)

    assert flow.state is FlowState.CREATED
    assert completed.state is FlowState.COMPLETED
    assert len(completed.history) == 4


def test_terminal_states_cannot_transition() -> None:
    flow = Flow(flow_id="flow-1", kind="fix").transition(FlowState.CANCELLED)

    with pytest.raises(InvalidTransitionError):
        flow.transition(FlowState.ACTIVE)


def test_plugin_extension_cannot_add_outgoing_transition_to_terminal_state() -> None:
    machine = FlowStateMachine.default()

    with pytest.raises(InvalidTransitionError):
        machine.extend([(FlowState.COMPLETED, FlowState.ACTIVE)])
