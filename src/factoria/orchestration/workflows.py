from __future__ import annotations

from dataclasses import dataclass

from .models import AgentRole, ModelProfile


@dataclass(frozen=True, slots=True)
class AgentStep:
    name: str
    role: AgentRole
    profile: ModelProfile | None = None
    preferred_tool: str | None = None
    agent_id: str | None = None


@dataclass(frozen=True, slots=True)
class AgentWorkflow:
    kind: str
    steps: tuple[AgentStep, ...]


class AgentWorkflowPlanner:
    @staticmethod
    def fix(*, large: bool = False, update_memory: bool = False) -> AgentWorkflow:
        steps: list[AgentStep] = [AgentStep("explore", AgentRole.EXPLORER)]
        if large:
            steps.append(AgentStep("plan", AgentRole.PLANNER))
        steps.extend(
            [
                AgentStep("implement", AgentRole.IMPLEMENTER),
                AgentStep("review", AgentRole.REVIEWER),
            ]
        )
        if update_memory:
            steps.append(AgentStep("document", AgentRole.DOCUMENTER))
        return AgentWorkflow(kind="fix", steps=tuple(steps))

    @staticmethod
    def feature() -> AgentWorkflow:
        return AgentWorkflow(
            kind="feature",
            steps=(
                AgentStep("explore", AgentRole.EXPLORER),
                AgentStep("plan", AgentRole.PLANNER),
                AgentStep("implement", AgentRole.IMPLEMENTER),
                AgentStep("review", AgentRole.REVIEWER),
                AgentStep("document", AgentRole.DOCUMENTER),
            ),
        )
