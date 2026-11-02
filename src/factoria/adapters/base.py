from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Protocol, Sequence

from factoria.domain.models import CheckResult
from factoria.security import SecretFinding, SecretScanner

from .argument_policy import AdapterArgumentPolicy, ArgumentPolicyError, DENY_ALL_ARGUMENTS


class ToolCapability(StrEnum):
    NON_INTERACTIVE = "non_interactive"
    STRUCTURED_OUTPUT = "structured_output"
    MODEL_SELECTION = "model_selection"
    PROJECT_DIRECTORY = "project_directory"
    READ_ONLY_ENFORCEMENT = "read_only_enforcement"
    PROJECT_WRITE_ENFORCEMENT = "project_write_enforcement"


@dataclass(frozen=True, slots=True)
class AgentRequest:
    prompt: str
    project_root: Path
    model: str | None = None
    structured_output: bool = False
    timeout_seconds: int = 1800
    # Compatibility field: these are never free-form. Every adapter must validate
    # them through an explicit AdapterArgumentPolicy before command construction.
    extra_args: tuple[str, ...] = field(default_factory=tuple)
    environment: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        if not self.prompt.strip():
            raise ValueError("Agent prompt cannot be empty")
        if self.timeout_seconds < 1:
            raise ValueError("Agent timeout must be positive")


@dataclass(frozen=True, slots=True)
class AgentResult:
    adapter: str
    command: tuple[str, ...]
    returncode: int | None
    stdout: str = ""
    stderr: str = ""
    error: str | None = None
    secret_findings: tuple[SecretFinding, ...] = field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        return self.returncode == 0 and self.error is None and not self.secret_findings


class ToolAdapter(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def executable(self) -> str: ...

    def capabilities(self) -> frozenset[ToolCapability]: ...

    def available(self) -> bool: ...

    def argument_policy(self) -> AdapterArgumentPolicy: ...

    def build_command(self, request: AgentRequest) -> tuple[str, ...]: ...

    def run(self, request: AgentRequest) -> AgentResult: ...

    def self_test(self) -> Sequence[CheckResult]: ...


def validate_adapter_args(adapter: object, args: tuple[str, ...]) -> tuple[str, ...]:
    """Validate externally supplied CLI arguments without trusting adapter defaults.

    Third-party adapters are trusted Python code, but Factoria will still never pass
    orchestration-supplied arguments to them unless they expose an explicit policy.
    """
    if not args:
        return ()
    policy_factory = getattr(adapter, "argument_policy", None)
    if not callable(policy_factory):
        raise ArgumentPolicyError(
            "Adapter does not declare an argument policy; Factoria refuses to pass extra arguments"
        )
    policy = policy_factory()
    if not isinstance(policy, AdapterArgumentPolicy):
        raise ArgumentPolicyError("Adapter returned an invalid argument policy")
    return policy.validate(args)


@dataclass(frozen=True, slots=True)
class SubprocessToolAdapter:
    executable: str
    max_output_chars: int = 50000
    secret_scanner: SecretScanner = SecretScanner()

    def available(self) -> bool:
        return shutil.which(self.executable) is not None

    def argument_policy(self) -> AdapterArgumentPolicy:
        return DENY_ALL_ARGUMENTS

    def _validated_extra_args(self, request: AgentRequest) -> tuple[str, ...]:
        return self.argument_policy().validate(request.extra_args)

    def _execute(self, request: AgentRequest, command: tuple[str, ...], *, adapter_name: str) -> AgentResult:
        root = request.project_root.expanduser().resolve()
        if not root.is_dir():
            return AgentResult(
                adapter=adapter_name,
                command=command,
                returncode=None,
                error=f"Project root does not exist: {root}",
            )
        if not self.available():
            return AgentResult(
                adapter=adapter_name,
                command=command,
                returncode=None,
                error=f"Executable not found: {self.executable}",
            )
        environment = os.environ.copy()
        environment.update(request.environment)
        try:
            completed = subprocess.run(
                list(command),
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=request.timeout_seconds,
                env=environment,
            )
        except subprocess.TimeoutExpired:
            return AgentResult(
                adapter=adapter_name,
                command=command,
                returncode=None,
                error=f"Agent timed out after {request.timeout_seconds}s",
            )
        except OSError as exc:
            return AgentResult(
                adapter=adapter_name,
                command=command,
                returncode=None,
                error=f"Agent could not start: {exc}",
            )

        stdout, stdout_findings = self.secret_scanner.redact(completed.stdout[-self.max_output_chars :])
        stderr, stderr_findings = self.secret_scanner.redact(completed.stderr[-self.max_output_chars :])
        return AgentResult(
            adapter=adapter_name,
            command=command,
            returncode=completed.returncode,
            stdout=stdout,
            stderr=stderr,
            secret_findings=stdout_findings + stderr_findings,
        )

    def _version_check(self, *, adapter_name: str) -> CheckResult:
        if not self.available():
            return CheckResult(
                name=f"{adapter_name}:installed",
                passed=False,
                required=True,
                details=f"Executable not found: {self.executable}",
            )
        try:
            completed = subprocess.run(
                [self.executable, "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return CheckResult(
                name=f"{adapter_name}:version",
                passed=False,
                required=True,
                details=str(exc),
            )
        output = (completed.stdout or completed.stderr).strip()
        sanitized, findings = self.secret_scanner.redact(output)
        if findings:
            return CheckResult(
                name=f"{adapter_name}:version",
                passed=False,
                required=True,
                details="Potential secret detected in tool version output; value redacted",
            )
        return CheckResult(
            name=f"{adapter_name}:version",
            passed=completed.returncode == 0,
            required=True,
            details=sanitized or f"exit={completed.returncode}",
        )

    def _help_capability_check(
        self,
        *,
        adapter_name: str,
        args: tuple[str, ...],
        required_tokens: tuple[str, ...],
    ) -> CheckResult:
        if not self.available():
            return CheckResult(
                name=f"{adapter_name}:capabilities",
                passed=False,
                required=True,
                details=f"Executable not found: {self.executable}",
            )
        try:
            completed = subprocess.run(
                [self.executable, *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return CheckResult(
                name=f"{adapter_name}:capabilities",
                passed=False,
                required=True,
                details=str(exc),
            )
        output = (completed.stdout or "") + "\n" + (completed.stderr or "")
        sanitized, findings = self.secret_scanner.redact(output)
        if findings:
            return CheckResult(
                name=f"{adapter_name}:capabilities",
                passed=False,
                required=True,
                details="Potential secret detected in tool help output; value redacted",
            )
        missing = tuple(token for token in required_tokens if token not in sanitized)
        passed = completed.returncode == 0 and not missing
        details = "supported" if passed else (
            "missing expected CLI flags: " + ", ".join(missing)
            if missing
            else f"help command exited with code {completed.returncode}"
        )
        return CheckResult(
            name=f"{adapter_name}:capabilities",
            passed=passed,
            required=True,
            details=details,
        )
