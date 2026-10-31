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


class ToolCapability(StrEnum):
    NON_INTERACTIVE = "non_interactive"
    STRUCTURED_OUTPUT = "structured_output"
    MODEL_SELECTION = "model_selection"
    PROJECT_DIRECTORY = "project_directory"


@dataclass(frozen=True, slots=True)
class AgentRequest:
    prompt: str
    project_root: Path
    model: str | None = None
    structured_output: bool = False
    timeout_seconds: int = 1800
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

    @property
    def passed(self) -> bool:
        return self.returncode == 0 and self.error is None


class ToolAdapter(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def executable(self) -> str: ...

    def capabilities(self) -> frozenset[ToolCapability]: ...

    def available(self) -> bool: ...

    def build_command(self, request: AgentRequest) -> tuple[str, ...]: ...

    def run(self, request: AgentRequest) -> AgentResult: ...

    def self_test(self) -> Sequence[CheckResult]: ...


@dataclass(frozen=True, slots=True)
class SubprocessToolAdapter:
    executable: str
    max_output_chars: int = 50000

    def available(self) -> bool:
        return shutil.which(self.executable) is not None

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

        return AgentResult(
            adapter=adapter_name,
            command=command,
            returncode=completed.returncode,
            stdout=completed.stdout[-self.max_output_chars :],
            stderr=completed.stderr[-self.max_output_chars :],
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
        return CheckResult(
            name=f"{adapter_name}:version",
            passed=completed.returncode == 0,
            required=True,
            details=output or f"exit={completed.returncode}",
        )
