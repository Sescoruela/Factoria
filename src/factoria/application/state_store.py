from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from factoria.domain.flow import Flow, FlowState, StateTransition

from .artifacts import FlowArtifactStore
from .flow_service import FlowExecution


def _quote(value: str) -> str:
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


@dataclass(frozen=True, slots=True)
class LocalFlowStateStore:
    artifacts: FlowArtifactStore

    def save(self, execution: FlowExecution) -> None:
        workspace = self.artifacts.ensure(execution.flow.flow_id)
        lines = [
            f"flow_id = {_quote(execution.flow.flow_id)}",
            f"kind = {_quote(execution.flow.kind)}",
            f"state = {_quote(execution.flow.state.value)}",
        ]
        if execution.label is not None:
            lines.append(f"label = {_quote(execution.label)}")
        for transition in execution.flow.history:
            lines.extend(
                [
                    "",
                    "[[history]]",
                    f"source = {_quote(transition.source.value)}",
                    f"target = {_quote(transition.target.value)}",
                    f"occurred_at = {_quote(transition.occurred_at.isoformat())}",
                ]
            )
            if transition.reason is not None:
                lines.append(f"reason = {_quote(transition.reason)}")
        workspace.state_file.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")

    def load(self, flow_id: str) -> FlowExecution:
        workspace = self.artifacts.workspace(flow_id)
        if not workspace.state_file.exists():
            raise FileNotFoundError(f"No persisted state for flow {flow_id}")
        with workspace.state_file.open("rb") as handle:
            data = tomllib.load(handle)

        history = tuple(
            StateTransition(
                source=FlowState(item["source"]),
                target=FlowState(item["target"]),
                occurred_at=datetime.fromisoformat(item["occurred_at"]),
                reason=item.get("reason"),
            )
            for item in data.get("history", [])
        )
        return FlowExecution(
            flow=Flow(
                flow_id=data["flow_id"],
                kind=data["kind"],
                state=FlowState(data["state"]),
                history=history,
            ),
            workspace=workspace,
            label=data.get("label"),
            project_root=self.artifacts.project_root,
        )

    def incomplete(self) -> tuple[FlowExecution, ...]:
        root = self.artifacts.work_root
        if not root.exists():
            return ()
        executions: list[FlowExecution] = []
        for state_file in sorted(root.glob("*/state.toml")):
            execution = self.load(state_file.parent.name)
            if not execution.is_terminal:
                executions.append(execution)
        return tuple(executions)
