from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping

from factoria.domain.flow import FlowState
from factoria.domain.permissions import PermissionProfile

from .flow_service import FlowExecution


class RuntimeStage(StrEnum):
    RUNNING = "running"
    AWAITING_PLAN_APPROVAL = "awaiting_plan_approval"
    AWAITING_FINAL_APPROVAL = "awaiting_final_approval"
    READY_FOR_COMMIT = "ready_for_commit"


class RuntimeStateError(RuntimeError):
    """Raised when runtime metadata contradicts the canonical FlowState."""


@dataclass(frozen=True, slots=True)
class LiveFlowSession:
    flow_id: str
    kind: str
    title: str
    branch: str
    preferred_tool: str | None
    runtime_stage: RuntimeStage | None
    large_fix: bool = False
    update_memory: bool = False
    base_permission_profile: str = PermissionProfile.NORMAL.value
    permission_profile: str = PermissionProfile.NORMAL.value
    permission_escalated: bool = False

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "LiveFlowSession":
        values = dict(data)
        raw_stage = values.pop("runtime_stage", None)
        legacy_phase = values.pop("phase", None)
        if raw_stage is None and legacy_phase not in {None, "blocked"}:
            raw_stage = legacy_phase
        try:
            stage = RuntimeStage(raw_stage) if raw_stage is not None else None
        except ValueError as exc:
            raise RuntimeStateError(f"Unsupported persisted runtime stage: {raw_stage}") from exc
        return cls(runtime_stage=stage, **values)

    def to_mapping(self) -> dict[str, Any]:
        data = asdict(self)
        stage = self.runtime_stage
        data["runtime_stage"] = stage.value if stage is not None else None
        return data


def validate_runtime_state(execution: FlowExecution, session: LiveFlowSession) -> None:
    state = execution.flow.state
    stage = session.runtime_stage
    if execution.flow.flow_id != session.flow_id:
        raise RuntimeStateError("Runtime metadata belongs to a different flow")
    if execution.flow.kind != session.kind:
        raise RuntimeStateError("Runtime metadata kind contradicts persisted flow kind")

    if state is FlowState.ACTIVE:
        if stage is not RuntimeStage.RUNNING:
            raise RuntimeStateError(
                f"Active flow requires runtime_stage=running, got {stage.value if stage else '-'}"
            )
        return
    if state is FlowState.PAUSED:
        allowed = {
            RuntimeStage.AWAITING_PLAN_APPROVAL,
            RuntimeStage.AWAITING_FINAL_APPROVAL,
            RuntimeStage.READY_FOR_COMMIT,
        }
        if stage not in allowed:
            raise RuntimeStateError(
                f"Paused flow has incompatible runtime stage: {stage.value if stage else '-'}"
            )
        return
    if state is FlowState.BLOCKED:
        if stage is not None:
            raise RuntimeStateError("Blocked flow must not persist a resumable runtime stage")
        return
    if state in {FlowState.COMPLETED, FlowState.CANCELLED}:
        if stage is not None:
            raise RuntimeStateError("Terminal flow must not persist a runtime stage")
        return
    if state is FlowState.CREATED and stage is not None:
        raise RuntimeStateError("Created flow must not have runtime progress metadata")


def load_live_session(path: Path, execution: FlowExecution | None = None) -> LiveFlowSession:
    if not path.exists():
        raise FileNotFoundError(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise RuntimeStateError(f"Unreadable live-flow metadata: {exc}") from exc
    if not isinstance(raw, dict):
        raise RuntimeStateError("Live-flow metadata must be a JSON object")
    session = LiveFlowSession.from_mapping(raw)
    if execution is not None:
        validate_runtime_state(execution, session)
    return session


def save_live_session(path: Path, session: LiveFlowSession) -> None:
    path.write_text(
        json.dumps(session.to_mapping(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
