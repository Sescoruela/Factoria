from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable

from factoria.adapters import AdapterRegistry, CodexAdapter, OpenCodeAdapter
from factoria.application.artifacts import FlowArtifactStore
from factoria.application.execution import ExecutionMode, SafeCheckExecutor, SubprocessCommandRunner
from factoria.application.flow_service import FlowExecution, FlowService
from factoria.application.quality import ReviewAction, ReviewGate
from factoria.application.review_runtime import (
    ReviewParseError,
    parse_structured_review,
    render_structured_review,
)
from factoria.application.runtime_state import (
    LiveFlowSession,
    RuntimeStage,
    RuntimeStateError,
    load_live_session,
    save_live_session,
    validate_runtime_state,
)
from factoria.application.state_store import LocalFlowStateStore
from factoria.domain.flow import FlowState
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
            runtime_stage=RuntimeStage.RUNNING,
            large_fix=large_fix,
            update_memory=update_memory,
            base_permission_profile=base_permission_profile.value,
            permission_profile=effective_profile.value,
            permission_escalated=escalated,
        )
        self._save_session(session, execution=execution)
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
            execution = self.service.pause(
                execution,
                reason="Plan generated; explicit approval is required before implementation",
            )
            session = replace(session, runtime_stage=RuntimeStage.AWAITING_PLAN_APPROVAL)
            self._save_session(session, execution=execution)
            return execution

        execution, passed = self._run_steps(
            execution,
            session,
            workflow.steps,
            project_root=project_root,
            memory=memory,
        )
        if not passed:
            return execution
        execution = self.service.pause(
            execution,
            reason="Agent work and structured review completed; inspect changes and commit manually",
        )
        session = replace(session, runtime_stage=RuntimeStage.READY_FOR_COMMIT)
        self._save_session(session, execution=execution)
        return execution

    def resume(
        self,
        *,
        flow_id: str,
        project_root: Path,
        approve_plan: bool = False,
        approve_final: bool = False,
    ) -> FlowExecution:
        execution = self.store.load(flow_id)
        session = self._load_session(flow_id, execution=execution)
        current_branch = _git(project_root, "branch", "--show-current").strip()
        if current_branch != session.branch:
            raise LiveAgentFlowError(
                f"Flow {flow_id} belongs to branch {session.branch!r}; current branch is {current_branch!r}"
            )
        if execution.flow.state is FlowState.BLOCKED:
            raise LiveAgentFlowError("Flow is blocked; inspect its artifacts before resuming")

        memory = load_project_memory(project_root)
        if session.runtime_stage is RuntimeStage.AWAITING_PLAN_APPROVAL:
            if not approve_plan:
                raise LiveAgentFlowError(
                    "Plan approval required; resume with --approve-plan after reviewing plan.md"
                )
            execution = self.service.resume(execution)
            session = replace(session, runtime_stage=RuntimeStage.RUNNING)
            self._save_session(session, execution=execution)
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
            execution = self.service.pause(
                execution,
                reason="Implementation and structured review finished; explicit final approval is required",
            )
            session = replace(session, runtime_stage=RuntimeStage.AWAITING_FINAL_APPROVAL)
            self._save_session(session, execution=execution)
            return execution

        if session.runtime_stage is RuntimeStage.AWAITING_FINAL_APPROVAL:
            if not approve_final:
                raise LiveAgentFlowError(
                    "Final approval required; resume with --approve-final after reviewing the result"
                )
            execution = self.service.resume(execution)
            session = replace(session, runtime_stage=RuntimeStage.RUNNING)
            self._save_session(session, execution=execution)
            if self._has_pending_changes(project_root):
                execution = self.service.pause(
                    execution,
                    reason="Final result approved; commit the reviewed changes manually",
                )
                session = replace(session, runtime_stage=RuntimeStage.READY_FOR_COMMIT)
                self._save_session(session, execution=execution)
                return execution
            self._save_session(replace(session, runtime_stage=None))
            return self.service.complete(execution)

        if session.runtime_stage is RuntimeStage.READY_FOR_COMMIT:
            if self._has_pending_changes(project_root):
                raise LiveAgentFlowError(
                    "Working tree still has pending changes; commit or intentionally resolve them before closing the flow"
                )
            execution = self.service.resume(execution)
            self._save_session(replace(session, runtime_stage=None))
            return self.service.complete(execution)

        raise LiveAgentFlowError(
            f"Unsupported persisted runtime stage: {session.runtime_stage.value if session.runtime_stage else '-'}"
        )

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
            if step.role is AgentRole.REVIEWER:
                execution, accepted = self._run_review_with_corrections(
                    execution,
                    session,
                    reviewer_step=step,
                    project_root=project_root,
                    memory=memory,
                )
                if not accepted:
                    return execution, False
                continue

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
                "document": "memory-proposal.md",
            }.get(step.name, f"{step.name}.txt")
            self.artifacts.write_text(
                session.flow_id,
                filename,
                result.result.stdout or result.result.stderr or result.result.error or "",
            )
            self._append_trace(session.flow_id, step.name, result.trace.attempts)
            if not result.trace.passed:
                return self._block(
                    execution,
                    session,
                    reason=f"Agent stage failed: {step.name}",
                )
            if step.role is AgentRole.IMPLEMENTER:
                if not self._verify(project_root, memory, session.flow_id):
                    return self._block(
                        execution,
                        session,
                        reason="A required confirmed verification failed",
                    )
        return execution, True

    def _run_review_with_corrections(
        self,
        execution: FlowExecution,
        session: LiveFlowSession,
        *,
        reviewer_step: AgentStep,
        project_root: Path,
        memory: ProjectMemory,
    ) -> tuple[FlowExecution, bool]:
        gate = ReviewGate(max_cycles=2)
        current_cycle = 0
        while True:
            result = self.orchestrator.run(
                AgentStage(
                    role=reviewer_step.role,
                    prompt=self._prompt(reviewer_step, session, memory),
                    profile=reviewer_step.profile,
                    preferred_tool=session.preferred_tool,
                ),
                project_root=project_root,
            )
            output = result.result.stdout or result.result.stderr or result.result.error or ""
            self.artifacts.write_text(session.flow_id, "review.md", output)
            self.artifacts.write_text(
                session.flow_id,
                f"review-cycle-{current_cycle}.md",
                output,
            )
            self._append_trace(
                session.flow_id,
                f"review-{current_cycle}",
                result.trace.attempts,
            )
            if not result.trace.passed:
                return self._block(
                    execution,
                    session,
                    reason=f"Reviewer agent failed during cycle {current_cycle}",
                )

            try:
                structured = parse_structured_review(output)
            except ReviewParseError as exc:
                self.artifacts.write_text(
                    session.flow_id,
                    "review-error.txt",
                    f"{exc}\n",
                )
                return self._block(
                    execution,
                    session,
                    reason=f"Reviewer output did not satisfy the structured contract: {exc}",
                )

            normalized = render_structured_review(structured)
            self.artifacts.write_text(session.flow_id, "review.json", normalized)
            self.artifacts.write_text(
                session.flow_id,
                f"review-cycle-{current_cycle}.json",
                normalized,
            )
            decision = gate.evaluate(structured.review, current_cycle=current_cycle)
            if decision.action is ReviewAction.ACCEPT:
                return execution, True
            if decision.action is ReviewAction.BLOCK:
                return self._block(
                    execution,
                    session,
                    reason=decision.reason or "Structured review still blocks closure",
                )

            correction_cycle = decision.next_cycle
            implementer = self._implementer_step(session)
            correction = self.orchestrator.run(
                AgentStage(
                    role=implementer.role,
                    prompt=self._correction_prompt(
                        implementer,
                        session,
                        memory,
                        structured=structured,
                        cycle=correction_cycle,
                    ),
                    profile=implementer.profile,
                    preferred_tool=session.preferred_tool,
                ),
                project_root=project_root,
            )
            self.artifacts.write_text(
                session.flow_id,
                f"correction-{correction_cycle}.txt",
                correction.result.stdout
                or correction.result.stderr
                or correction.result.error
                or "",
            )
            self._append_trace(
                session.flow_id,
                f"correction-{correction_cycle}",
                correction.trace.attempts,
            )
            if not correction.trace.passed:
                return self._block(
                    execution,
                    session,
                    reason=f"Correction cycle {correction_cycle} failed",
                )
            if not self._verify(project_root, memory, session.flow_id):
                return self._block(
                    execution,
                    session,
                    reason=f"Verification failed after correction cycle {correction_cycle}",
                )
            current_cycle = correction_cycle

    def _implementer_step(self, session: LiveFlowSession) -> AgentStep:
        for step in self._workflow(session).steps:
            if step.role is AgentRole.IMPLEMENTER:
                return step
        raise LiveAgentFlowError("Workflow does not define an implementer for review correction")

    def _correction_prompt(
        self,
        step: AgentStep,
        session: LiveFlowSession,
        memory: ProjectMemory,
        *,
        structured,
        cycle: int,
    ) -> str:
        findings = [
            f"- {finding.severity.value}: {finding.message}"
            + (f" (rule: {finding.rule})" if finding.rule else "")
            for finding in structured.review.findings
            if finding.severity.value in {"critical", "important"}
        ]
        findings.extend(
            f"- mandatory rule violated: {rule}"
            for rule in structured.review.mandatory_rules_violated
        )
        if not structured.review.acceptance_criteria_met:
            findings.append("- acceptance criteria are not fully satisfied")
        blocking = "\n".join(findings) or "- reviewer requested changes"
        return (
            self._prompt(step, session, memory)
            + f"\nThis is automatic review correction cycle {cycle} of 2.\n"
            + "Correct only the blocking reviewer findings below; do not expand scope.\n"
            + blocking
            + "\nAfter editing, stop. Factoria will run confirmed verification and review again."
        )

    def _block(
        self,
        execution: FlowExecution,
        session: LiveFlowSession,
        *,
        reason: str,
    ) -> tuple[FlowExecution, bool]:
        blocked_execution = self.service.block(execution, reason=reason)
        self._save_session(replace(session, runtime_stage=None), execution=blocked_execution)
        return blocked_execution, False

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
            "review": (
                "Review the current diff against the task, plan/acceptance criteria when present, mandatory rules, "
                "and verification evidence. Do not modify files. Return ONLY one JSON object with exactly these "
                "fields: result ('approved' or 'changes_required'), acceptance_criteria_met (boolean), "
                "mandatory_rules_violated (array of strings), findings (array of objects with severity "
                "'critical'|'important'|'minor', message, rule string or null), risks (array of strings), and "
                "recommendation (non-empty string). Critical, important, mandatory-rule violations, or unmet "
                "acceptance criteria require result='changes_required'; minor findings alone do not block."
            ),
            "document": "Propose memory/documentation updates caused by the change. Do not write files; Factoria will handle approved memory updates separately.",
        }
        if step.name == "implement" and self.artifacts.workspace(session.flow_id).plan_file.exists():
            base += f"Read .factoria/work/{session.flow_id}/plan.md before implementing.\n"
        if step.name == "review":
            base += f"Read .factoria/work/{session.flow_id}/verification.md and plan.md if it exists.\n"
        return base + instructions[step.name]

    def _prepare_branch(self, project_root: Path, *, requested: str | None) -> str:
        if self._has_pending_changes(project_root):
            raise LiveAgentFlowError("Working tree must be clean before starting a new flow")
        current = _git(project_root, "branch", "--show-current").strip()
        if not current:
            raise LiveAgentFlowError("Detached HEAD is not supported for Factoria flows")
        if current == "main":
            if not requested:
                raise LiveAgentFlowError(
                    "Flows never modify main directly; provide --branch with the branch name to create"
                )
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

    def _save_session(
        self,
        session: LiveFlowSession,
        *,
        execution: FlowExecution | None = None,
    ) -> None:
        workspace = self.artifacts.ensure(session.flow_id)
        if execution is not None:
            try:
                validate_runtime_state(execution, session)
            except RuntimeStateError as exc:
                raise LiveAgentFlowError(str(exc)) from exc
        save_live_session(workspace.root / "agent-flow.json", session)

    def _load_session(
        self,
        flow_id: str,
        *,
        execution: FlowExecution | None = None,
    ) -> LiveFlowSession:
        path = self._session_path(flow_id)
        if not path.exists():
            raise LiveAgentFlowError(f"Flow {flow_id} does not have live-agent session metadata")
        try:
            return load_live_session(path, execution=execution)
        except (RuntimeStateError, FileNotFoundError) as exc:
            raise LiveAgentFlowError(str(exc)) from exc

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
    aliases = {
        ModelProfile.RAPIDO: "FAST",
        ModelProfile.EQUILIBRADO: "BALANCED",
        ModelProfile.POTENTE: "POWERFUL",
    }
    for adapter in ("codex", "opencode"):
        profiles: dict[ModelProfile, str] = {}
        for profile, alias in aliases.items():
            canonical = os.environ.get(
                f"FACTORIA_{adapter.upper()}_{profile.value.upper()}"
            )
            compatibility = os.environ.get(
                f"FACTORIA_{adapter.upper()}_MODEL_{alias}"
            )
            value = canonical or compatibility
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
