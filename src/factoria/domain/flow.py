from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Iterable, Mapping


class InvalidTransitionError(ValueError):
    """Raised when a flow attempts an invalid state transition."""


class FlowState(StrEnum):
    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class StateTransition:
    source: FlowState
    target: FlowState
    occurred_at: datetime
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class FlowStateMachine:
    transitions: Mapping[FlowState, frozenset[FlowState]]

    @classmethod
    def default(cls) -> FlowStateMachine:
        return cls(
            MappingProxyType(
                {
                    FlowState.CREATED: frozenset({FlowState.ACTIVE, FlowState.CANCELLED}),
                    FlowState.ACTIVE: frozenset(
                        {
                            FlowState.PAUSED,
                            FlowState.BLOCKED,
                            FlowState.COMPLETED,
                            FlowState.CANCELLED,
                        }
                    ),
                    FlowState.PAUSED: frozenset({FlowState.ACTIVE, FlowState.CANCELLED}),
                    FlowState.BLOCKED: frozenset(
                        {FlowState.ACTIVE, FlowState.PAUSED, FlowState.CANCELLED}
                    ),
                    FlowState.COMPLETED: frozenset(),
                    FlowState.CANCELLED: frozenset(),
                }
            )
        )

    def can_transition(self, source: FlowState, target: FlowState) -> bool:
        return target in self.transitions.get(source, frozenset())

    def validate_extension(self, edges: Iterable[tuple[FlowState, FlowState]]) -> None:
        terminal = {FlowState.COMPLETED, FlowState.CANCELLED}
        for source, target in edges:
            if source in terminal:
                raise InvalidTransitionError(f"Terminal state {source} cannot have outgoing edges")
            if source == target:
                raise InvalidTransitionError("Self-transitions are not allowed")

    def extend(self, edges: Iterable[tuple[FlowState, FlowState]]) -> FlowStateMachine:
        edges = tuple(edges)
        self.validate_extension(edges)
        mutable = {state: set(targets) for state, targets in self.transitions.items()}
        for source, target in edges:
            mutable.setdefault(source, set()).add(target)
            mutable.setdefault(target, set())
        return FlowStateMachine(
            MappingProxyType({state: frozenset(targets) for state, targets in mutable.items()})
        )


@dataclass(frozen=True, slots=True)
class Flow:
    flow_id: str
    kind: str
    state: FlowState = FlowState.CREATED
    history: tuple[StateTransition, ...] = field(default_factory=tuple)

    def transition(
        self,
        target: FlowState,
        *,
        machine: FlowStateMachine | None = None,
        reason: str | None = None,
        occurred_at: datetime | None = None,
    ) -> Flow:
        machine = machine or FlowStateMachine.default()
        if not machine.can_transition(self.state, target):
            raise InvalidTransitionError(f"Invalid transition: {self.state} -> {target}")

        event = StateTransition(
            source=self.state,
            target=target,
            occurred_at=occurred_at or datetime.now(UTC),
            reason=reason,
        )
        return replace(self, state=target, history=(*self.history, event))
