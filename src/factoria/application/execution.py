from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from factoria.application.quality import CheckPlanner, CheckSpec
from factoria.domain.fix import VerificationResult
from factoria.domain.models import ConfirmedCommand, ProjectMemory
from factoria.security import SecretFinding, SecretScanner


class ExecutionMode(StrEnum):
    READ_ONLY = "read_only"
    SAFE_CHECKS = "safe_checks"
    NORMAL = "normal"


@dataclass(frozen=True, slots=True)
class CommandExecution:
    name: str
    category: str
    scope: str | None
    command: tuple[str, ...]
    required: bool
    returncode: int | None
    stdout: str = ""
    stderr: str = ""
    error: str | None = None
    secret_findings: tuple[SecretFinding, ...] = field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        return self.returncode == 0 and self.error is None and not self.secret_findings

    def to_verification_result(self) -> VerificationResult:
        detail = self.error
        if self.secret_findings:
            detail = "Potential secret detected in command output; output was redacted and the flow must remain blocked"
        elif detail is None and not self.passed:
            detail = f"Command exited with code {self.returncode}"
        return VerificationResult(
            name=self.name,
            passed=self.passed,
            required=self.required,
            details=detail,
        )


class CommandRunner(Protocol):
    def run(
        self, command: ConfirmedCommand, *, cwd: Path, timeout_seconds: int
    ) -> CommandExecution: ...


@dataclass(frozen=True, slots=True)
class SubprocessCommandRunner:
    max_output_chars: int = 8000
    secret_scanner: SecretScanner = SecretScanner()

    def run(
        self, command: ConfirmedCommand, *, cwd: Path, timeout_seconds: int
    ) -> CommandExecution:
        name = _command_name(command)
        try:
            result = subprocess.run(
                list(command.command),
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return CommandExecution(
                name=name,
                category=command.category,
                scope=command.scope,
                command=command.command,
                required=command.required,
                returncode=None,
                error=f"Command timed out after {timeout_seconds}s",
            )
        except OSError as exc:
            return CommandExecution(
                name=name,
                category=command.category,
                scope=command.scope,
                command=command.command,
                required=command.required,
                returncode=None,
                error=f"Command could not start: {exc}",
            )

        stdout, stdout_findings = self.secret_scanner.redact(
            result.stdout[-self.max_output_chars :]
        )
        stderr, stderr_findings = self.secret_scanner.redact(
            result.stderr[-self.max_output_chars :]
        )
        return CommandExecution(
            name=name,
            category=command.category,
            scope=command.scope,
            command=command.command,
            required=command.required,
            returncode=result.returncode,
            stdout=stdout,
            stderr=stderr,
            secret_findings=stdout_findings + stderr_findings,
        )


@dataclass(frozen=True, slots=True)
class SafeCheckPlan:
    affected_modules: tuple[str, ...]
    commands: tuple[ConfirmedCommand, ...]


@dataclass(frozen=True, slots=True)
class SafeCheckSummary:
    plan: SafeCheckPlan
    executions: tuple[CommandExecution, ...] = field(default_factory=tuple)

    @property
    def verification_results(self) -> tuple[VerificationResult, ...]:
        return tuple(item.to_verification_result() for item in self.executions)

    @property
    def secret_findings(self) -> tuple[SecretFinding, ...]:
        return tuple(
            finding for execution in self.executions for finding in execution.secret_findings
        )


@dataclass(frozen=True, slots=True)
class SafeCheckExecutor:
    runner: CommandRunner
    timeout_seconds: int = 300

    def plan(
        self,
        memory: ProjectMemory,
        *,
        changed_files: tuple[str, ...],
        categories: tuple[str, ...] | None = None,
    ) -> SafeCheckPlan:
        commands = _confirmed_commands(memory)
        if categories is not None:
            allowed = set(categories)
            commands = tuple(command for command in commands if command.category in allowed)

        specs = tuple(
            CheckSpec(
                name=_command_name(command),
                category=command.category,
                scope=command.scope,
                required=command.required,
                global_check=command.global_check,
            )
            for command in commands
        )
        check_plan = CheckPlanner(memory).plan(changed_files, specs)
        selected_names = {check.name for check in check_plan.checks}
        selected = tuple(
            command for command in commands if _command_name(command) in selected_names
        )
        return SafeCheckPlan(affected_modules=check_plan.affected_modules, commands=selected)

    def execute(
        self,
        memory: ProjectMemory,
        *,
        project_root: Path,
        changed_files: tuple[str, ...],
        mode: ExecutionMode = ExecutionMode.SAFE_CHECKS,
        categories: tuple[str, ...] | None = None,
    ) -> SafeCheckSummary:
        root = project_root.resolve()
        if mode is ExecutionMode.READ_ONLY:
            raise PermissionError("read-only mode forbids all project command execution")
        if not root.is_dir():
            raise FileNotFoundError(f"Project root does not exist: {root}")

        plan = self.plan(memory, changed_files=changed_files, categories=categories)
        executions = tuple(
            self.runner.run(command, cwd=root, timeout_seconds=self.timeout_seconds)
            for command in plan.commands
        )
        return SafeCheckSummary(plan=plan, executions=executions)


def _confirmed_commands(memory: ProjectMemory) -> tuple[ConfirmedCommand, ...]:
    if memory.confirmed_check_commands:
        return memory.confirmed_check_commands

    legacy: list[ConfirmedCommand] = []
    for category, commands in memory.confirmed_commands.items():
        for command in commands:
            legacy.append(ConfirmedCommand(category=category, command=command))
    return tuple(legacy)


def _command_name(command: ConfirmedCommand) -> str:
    scope = command.scope or "global"
    argv = " ".join(command.command)
    return f"{command.category}:{scope}:{argv}"
