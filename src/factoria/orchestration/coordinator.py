from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from .models import AgentStage
from .orchestrator import AgentOrchestrator, AgentStageResult
from .workflows import AgentWorkflow


@dataclass(frozen=True, slots=True)
class FlowAgentRun:
    kind: str
    results: tuple[AgentStageResult, ...] = field(default_factory=tuple)
    stopped_at: str | None = None

    @property
    def passed(self) -> bool:
        return self.stopped_at is None and all(item.trace.passed for item in self.results)


@dataclass(frozen=True, slots=True)
class FlowAgentCoordinator:
    orchestrator: AgentOrchestrator

    def run(
        self,
        workflow: AgentWorkflow,
        *,
        prompts: Mapping[str, str],
        project_root: Path,
        preferred_tool: str | None = None,
    ) -> FlowAgentRun:
        results: list[AgentStageResult] = []
        for step in workflow.steps:
            prompt = prompts.get(step.name)
            if prompt is None or not prompt.strip():
                raise ValueError(f"Missing prompt for workflow step: {step.name}")
            result = self.orchestrator.run(
                AgentStage(
                    role=step.role,
                    prompt=prompt,
                    profile=step.profile,
                    preferred_tool=preferred_tool,
                ),
                project_root=project_root,
            )
            results.append(result)
            if not result.trace.passed:
                return FlowAgentRun(
                    kind=workflow.kind,
                    results=tuple(results),
                    stopped_at=step.name,
                )
        return FlowAgentRun(kind=workflow.kind, results=tuple(results))
