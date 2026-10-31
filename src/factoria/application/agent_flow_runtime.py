from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Iterable

from factoria.adapters import AdapterRegistry, CodexAdapter, OpenCodeAdapter
from factoria.application.artifacts import FlowArtifactStore
from factoria.application.execution import ExecutionMode, SafeCheckExecutor, SubprocessCommandRunner
from factoria.application.flow_service import FlowExecution, FlowService
from factoria.application.state_store import LocalFlowStateStore
from factoria.domain.models import ProjectMemory
from factoria.domain.permissions import PermissionProfile
from factoria.memory.loader import load_project_memory
from factoria.orchestration import (
    AdapterSafetyPolicy,
    AgentOrchestrator,
    AgentRole,
    AgentStage,
    AgentStep,
    AgentWorkflowPlanner,
    ModelProfile,
    ModelRouter,
    RetryPolicy,
    RoleAccess,
)


@dataclass(frozen=True, slots=True)
class LiveFlowSession:
    flow_id: str
    kind: str
    title: str
    branch: str
    preferred_tool: str | None
    phase: str
    large_fix: bool = False
    update_memory: bool = False
    base_permission_profile: str = PermissionProfile.NORMAL.value
    permission_profile: str = PermissionProfile.NORMAL.value
    permission_escalated: bool = False


class LiveAgentFlowError(RuntimeError):
    """Raised when a live agent flow cannot continue safely."""


@dataclass(frozen=True, slots=True)
class LiveAgentFlowRunner:
    service: FlowService
    store: LocalFlowStateStore
    artifacts: FlowArtifactStore
    orchestrator: AgentOrchestrator
    check_executor: SafeCheckExecutor

    def start(
        self,
        *,
        kind: str,
        title: str,
        project_root: Path,
        flow_id: str,
        branch: str | None,
        preferred_tool: str | None = None,
        label: str | None = None,
        large_fix: bool = False,
        update_memory: bool = False,
        base_permission_profile: PermissionProfile = PermissionProfile.NORMAL,
        requested_permission_profile: PermissionProfile | None = None,
    ) -> FlowExecution:
        if kind not in {"fix", "feature"}:
            raise ValueError(f"Unsupported live flow kind: {kind}")
        memory = load_project_memory(project_root)
        flow_branch = self._prepare_branch(project_root, requested=branch)
        execution = self.service.create(
            flow_id=flow_id,
            kind=kind,
            label=label or title,
        )
        self.artifacts.write_text(flow_id, "task.md", f"# {kind.title()}\n\n{title}\n")
        execution = self.service.start(execution)
        effective_profile = requested_permission_profile or base_permission_profile
        escalated = _profile_rank(effective_profile) > _profile_rank(base_permission_profile)
        gated = kind == "feature" or large_fix
        session = LiveFlowSession(
            flow_id=flow_id,
            kind=kind,
            title=title,
            branch=flow_branch,
            preferred_tool=preferred_tool,
            phase="running",
            large_fix=large_fix,
            update_memory=update_memory,
            base_permission_profile=base_permission_profile.value,
            permission_profile=effective_profile.value,
            permission_escalated=escalated,
        )
        self._save_session(session)
        self.artifacts.write_text(
            flow_id,
            "permissions.json",
            json.dumps(
                {
                    "base_profile": base_permission_profile.value,
                    "effective_profile": effective_profile.value,
                    "temporary_escalation": escalated,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )

        workflow = self._workflow(session)
        if gated:
            before_approval = tuple(
                step for step in workflow.steps if step.name in {"explore", "plan"}
            )
            execution, passed = self._run_steps(
                execution,
                session,
                before_approval,
                project_root=project_root,
                memory=memory,
            )
            if not passed:
                return execution
            session = replace(session, phase="awaiting_plan_approval")
            self._save_session(session)
            return self.service.pause(
                execution,
                reason="Plan generated; explicit approval is required before implementation",
            )

        execution, passed = self._run_steps(
            execution,
            session,
            workflow.steps,
            project_root=project_root,
            memory=memory,
        )
        if not passed:
            return execution
        session = replace(session, phase="ready_for_commit")
        self._save_session(session)
        return self.service.pause(
            execution,
            reason="Agent work and review completed; inspect changes and commit manually",
        )

    def resume(
        self,
        *,
        flow_id: str,
        project_root: Path,
        approve_plan: bool = False,
        approve_final: bool = False,
    ) -> FlowExecution:
        session = self._load_session(flow_id)
        execution = self.store.load(flow_id)
        current_branch = _git(project_root, "branch", "--show-current").strip()
        if current_branch != session.branch:
            raise LiveAgentFlowError(
                f"Flow {flow_id} belongs to branch {session.branch!r}; current branch is {current_branch!r}"
            )
        if session.phase == "blocked":
            raise LiveAgentFlowError("Flow is blocked; inspect its artifacts before resuming")

        memory = load_project_memory(project_root)
        if session.phase == "awaiting_plan_approval":
            if not approve_plan:
                raise LiveAgentFlowError("Plan approval required; resume with --approve-plan after reviewing plan.md")
            execution = self.service.resume(execution)
            remaining = tuple(
                step
                for step in self._workflow(session).steps
                if step.name not in {"explore", "plan"}
            )
            execution, passed = self._run_steps(
                execution,
                session,
                remaining,
                project_root=project_root,
                memory=memory,
            )
            if not passed:
                return execution
            session = replace(session, phase="awaiting_final_approval")
            self._save_session(session)
            return self.service.pause(
                execution,
                reason="Implementation and review finished; explicit final approval is required",
            )

        if session.phase == "awaiting_final_approval":
            if not approve_final:
                raise LiveAgentFlowError("Final approval required; resume with --approve-final after reviewing the result")
            execution = self.service.resume(execution)
            if self._has_pending_changes(project_root):
                session = replace(session, phase="ready_for_commit")
                self._save_session(session)
                return self.service.pause(
                    execution,
                    reason="Final result approved; commit the reviewed changes manually",
                )
            return self.service.complete(execution)

        if session.phase == "ready_for_commit":
            if self._has_pending_changes(project_root):
                raise LiveAgentFlowError(
                    "Working tree still has pending changes; commit or intentionally resolve them before closing the flow"
                )
            execution = self.service.resume(execution)
            return self.service.complete(execution)

        raise LiveAgentFlowError(f"Unsupported persisted live-flow phase: {session.phase}")

    def _run_steps(
        self,
        execution: FlowExecution,
        session: LiveFlowSession,
        steps: Iterable[AgentStep],
        *,
        project_root: Path,
        memory: ProjectMemory,
    ) -> tuple[FlowExecution, bool]:
        for step in steps:
            result = self.orchestrator.run(
                AgentStage(
                    role=step.role,
                    prompt=self._prompt(step, session, memory),
                    profile=step.profile,
                    preferred_tool=session.preferred_tool,
                ),
                project_root=project_root,
            )
            filename = {
                "plan": "plan.md",
                "review": "review.md",
                "document": "memory-proposal.md",
            }.get(step.name, f"{step.name}.txt")
            self.artifacts.write_text(
                session.flow_id,
                filename,
                result.result.stdout or result.result.stderr or result.result.error or "",
            )
            self._append_trace(session.flow_id, step.name, result.trace.attempts)
            if not result.trace.passed:
                blocked = replace(session, phase="blocked")
                self._save_session(blocked)
                return (
                    self.service.block(
                        execution,
                        reason=f"Agent stage failed: {step.name}",
                    ),
                    False,
                )
            if step.role is AgentRole.IMPLEMENTER:
                verification_ok = self._verify(project_root, memory, session.flow_id)
                if not verification_ok:
                    blocked = replace(session, phase="blocked")
                    self._save_session(blocked)
                    return (
                        self.service.block(
                            execution,
                            reason="A required confirmed verification failed",
                        ),
                        False,
                    )
        return execution, True

    def _verify(self, project_root: Path, memory: ProjectMemory, flow_id: str) -> bool:
        changed = self._changed_files(project_root)
        summary = self.check_executor.execute(
            memory,
            project_root=project_root,
            changed_files=changed,
            mode=ExecutionMode.SAFE_CHECKS,
        )
        lines = [
            "# Verification",
            "",
            f"Affected modules: {', '.join(summary.plan.affected_modules) or 'none detected'}",
        ]
        if summary.executions:
            for item in summary.executions:
                status = "PASS" if item.passed else "FAIL"
                lines.append(f"- {status} {item.name}")
        else:
            lines.append("- No confirmed automated checks selected.")
            if memory.manual_verification:
                lines.append("- Manual verification required:")
                lines.extend(f"  - {item}" for item in memory.manual_verification)
        self.artifacts.write_text(flow_id, "verification.md", "\n".join(lines) + "\n")
        return all(item.passed or not item.required for item in summary.executions)

    def _workflow(self, session: LiveFlowSession):
        if session.kind == "feature":
            return AgentWorkflowPlanner.feature()
        return AgentWorkflowPlanner.fix(
            large=session.large_fix,
            update_memory=session.update_memory,
        )

    def _prompt(self, step: AgentStep, session: LiveFlowSession, memory: ProjectMemory) -> str:
        rules = "\n".join(f"- {rule}" for rule in memory.mandatory_rules) or "- No mandatory rules recorded"
        base = (
            f"You are the {step.role.value} for a Factoria {session.kind} flow.\n"
            f"Task: {session.title}\n"
            f"Project: {memory.project_name}\n"
            f"Mandatory rules:\n{rules}\n"
            "Never commit, push, open a PR, access secrets, or modify anything outside the project.\n"
        )
        instructions = {
            "explore": "Inspect the repository and explain the relevant code, likely impact, and risks. Do not modify files.",
            "plan": "Produce an implementation plan with acceptance criteria, affected modules, risks, and verification. Do not modify files.",
            "implement": "Implement only the approved task with the smallest maintainable change. Do not run project commands; Factoria runs confirmed checks separately.",
            "review": "Review the current diff against the task, mandatory rules, and verification evidence. Report critical, important, and minor findings. Do not modify files.",
            "document": "Propose memory/documentation updates caused by the change. Do not write files; Factoria will handle approved memory updates separately.",
        }
        if step.name == "implement" and self.artifacts.workspace(session.flow_id).plan_file.exists():
            base += f"Read .factoria/work/{session.flow_id}/plan.md before implementing.\n"
        return base + instructions[step.name]

    def _prepare_branch(self, project_root: Path, *, requested: str | None) -> str:
        if self._has_pending_changes(project_root):
            raise LiveAgentFlowError("Working tree must be clean before starting a new flow")
        current = _git(project_root, "branch", "--show-current").strip()
        if not current:
            raise LiveAgentFlowError("Detached HEAD is not supported for Factoria flows")
        if current == "main":
            if not requested:
                raise LiveAgentFlowError("Flows never modify main directly; provide --branch with the branch name to create")
            _git(project_root, "switch", "-c", requested)
            return requested
        if requested and requested != current:
            _git(project_root, "switch", "-c", requested)
            return requested
        return current

    @staticmethod
    def _has_pending_changes(project_root: Path) -> bool:
        return bool(_git(project_root, "status", "--porcelain").strip())

    @staticmethod
    def _changed_files(project_root: Path) -> tuple[str, ...]:
        changed: list[str] = []
        for raw in _git(project_root, "status", "--porcelain").splitlines():
            if len(raw) < 4:
                continue
            path = raw[3:]
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            changed.append(path.strip('"'))
        return tuple(dict.fromkeys(changed))

    def _session_path(self, flow_id: str) -> Path:
        return self.artifacts.workspace(flow_id).root / "agent-flow.json"

    def _save_session(self, session: LiveFlowSession) -> None:
        workspace = self.artifacts.ensure(session.flow_id)
        (workspace.root / "agent-flow.json").write_text(
            json.dumps(asdict(session), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _load_session(self, flow_id: str) -> LiveFlowSession:
        path = self._session_path(flow_id)
        if not path.exists():
            raise LiveAgentFlowError(f"Flow {flow_id} does not have live-agent session metadata")
        return LiveFlowSession(**json.loads(path.read_text(encoding="utf-8")))

    def _append_trace(self, flow_id: str, step_name: str, attempts) -> None:
        path = self.artifacts.ensure(flow_id).root / "agents.log"
        lines = []
        for item in attempts:
            lines.append(
                f"step={step_name} role={item.role.value} attempt={item.attempt} "
                f"adapter={item.adapter} profile={item.profile.value} model={item.model or 'default'} "
                f"fallback={str(item.fallback).lower()} passed={str(item.passed).lower()}"
            )
        with path.open("a", encoding="utf-8", newline="") as handle:
            handle.write("\n".join(lines) + "\n")


def default_live_orchestrator() -> AgentOrchestrator:
    registry = AdapterRegistry()
    registry.register(CodexAdapter())
    registry.register(OpenCodeAdapter())
    read_only_args = ("--sandbox", "read-only", "--ask-for-approval", "never")
    read_only_roles = (
        AgentRole.EXPLORER,
        AgentRole.PLANNER,
        AgentRole.REVIEWER,
        AgentRole.DOCUMENTER,
    )
    opencode_read_only = json.dumps(
        {
            "*": "deny",
            "read": "allow",
            "glob": "allow",
            "grep": "allow",
            "lsp": "allow",
        },
        separators=(",", ":"),
    )
    opencode_implementer = json.dumps(
        {
            "*": "deny",
            "read": "allow",
            "glob": "allow",
            "grep": "allow",
            "lsp": "allow",
            "edit": "allow",
        },
        separators=(",", ":"),
    )
    safety = AdapterSafetyPolicy(
        restricted_access={
            "codex": frozenset({RoleAccess.READ_ONLY}),
            "opencode": frozenset({RoleAccess.READ_ONLY}),
        },
        denied_access={"codex": frozenset({RoleAccess.PROJECT_WRITE})},
        role_args={
            "codex": {role: read_only_args for role in read_only_roles},
        },
        role_environment={
            "opencode": {
                **{role: {"OPENCODE_PERMISSION": opencode_read_only} for role in read_only_roles},
                AgentRole.IMPLEMENTER: {"OPENCODE_PERMISSION": opencode_implementer},
            }
        },
    )
    return AgentOrchestrator(
        registry=registry,
        model_router=_model_router_from_environment(),
        safety_policy=safety,
        retry_policy=RetryPolicy(max_attempts=2, escalate_profile=True),
    )


def build_live_runner(project_root: Path) -> LiveAgentFlowRunner:
    artifacts = FlowArtifactStore(project_root)
    store = LocalFlowStateStore(artifacts)
    service = FlowService(artifacts=artifacts, state_store=store)
    return LiveAgentFlowRunner(
        service=service,
        store=store,
        artifacts=artifacts,
        orchestrator=default_live_orchestrator(),
        check_executor=SafeCheckExecutor(SubprocessCommandRunner()),
    )


def _model_router_from_environment() -> ModelRouter:
    mapping: dict[str, dict[ModelProfile, str]] = {}
    for adapter in ("codex", "opencode"):
        profiles: dict[ModelProfile, str] = {}
        for profile, suffix in (
            (ModelProfile.RAPIDO, "FAST"),
            (ModelProfile.EQUILIBRADO, "BALANCED"),
            (ModelProfile.POTENTE, "POWERFUL"),
        ):
            value = os.environ.get(f"FACTORIA_{adapter.upper()}_MODEL_{suffix}")
            if value:
                profiles[profile] = value
        if profiles:
            mapping[adapter] = profiles
    return ModelRouter(mapping=mapping)


def _profile_rank(profile: PermissionProfile) -> int:
    return {
        PermissionProfile.SAFE: 0,
        PermissionProfile.NORMAL: 1,
        PermissionProfile.POWER: 2,
    }[profile]


def _git(project_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(project_root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout
