from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Protocol, Sequence

from factoria.domain.flow import Flow, FlowState

from .artifacts import FlowArtifactStore, FlowWorkspace


class FlowStateStore(Protocol):
    def save(self, execution: "FlowExecution") -> None: ...

    def incomplete(self) -> Sequence["FlowExecution"]: ...


@dataclass(frozen=True, slots=True)
class FlowExecution:
    flow: Flow
    workspace: FlowWorkspace
    label: str | None = None
    project_root: Path | None = None

    @property
    def is_terminal(self) -> bool:
        return self.flow.state in {FlowState.COMPLETED, FlowState.CANCELLED}


@dataclass(frozen=True, slots=True)
class FlowService:
    artifacts: FlowArtifactStore
    state_store: FlowStateStore | None = None

    def create(self, *, flow_id: str, kind: str, label: str | None = None) -> FlowExecution:
        if self.state_store is not None:
            running = tuple(self.state_store.incomplete())
            if running:
                active = ", ".join(item.flow.flow_id for item in running)
                raise RuntimeError(
                    f"Project already has an incomplete flow ({active}); resume or cancel it first"
                )

        workspace = self.artifacts.ensure(flow_id)
        execution = FlowExecution(
            flow=Flow(flow_id=flow_id, kind=kind),
            workspace=workspace,
            label=label,
            project_root=self.artifacts.project_root,
        )
        self._persist(execution)
        return execution

    def start(self, execution: FlowExecution) -> FlowExecution:
        return self._transition(execution, FlowState.ACTIVE)

    def pause(self, execution: FlowExecution, *, reason: str | None = None) -> FlowExecution:
        return self._transition(execution, FlowState.PAUSED, reason=reason)

    def resume(self, execution: FlowExecution) -> FlowExecution:
        return self._transition(execution, FlowState.ACTIVE)

    def block(self, execution: FlowExecution, *, reason: str) -> FlowExecution:
        return self._transition(execution, FlowState.BLOCKED, reason=reason)

    def complete(self, execution: FlowExecution) -> FlowExecution:
        completed = self._transition(execution, FlowState.COMPLETED)
        self.artifacts.cleanup(completed.flow.flow_id)
        return completed

    def cancel(self, execution: FlowExecution, *, reason: str | None = None) -> FlowExecution:
        cancelled = self._transition(execution, FlowState.CANCELLED, reason=reason)
        self.artifacts.cleanup(cancelled.flow.flow_id)
        return cancelled

    def relabel(self, execution: FlowExecution, label: str | None) -> FlowExecution:
        updated = replace(execution, label=label)
        self._persist(updated)
        return updated

    def _transition(
        self,
        execution: FlowExecution,
        target: FlowState,
        *,
        reason: str | None = None,
        occurred_at: datetime | None = None,
    ) -> FlowExecution:
        flow = execution.flow.transition(target, reason=reason, occurred_at=occurred_at)
        updated = replace(execution, flow=flow)
        self._persist(updated)
        return updated

    def _persist(self, execution: FlowExecution) -> None:
        if self.state_store is not None:
            self.state_store.save(execution)
