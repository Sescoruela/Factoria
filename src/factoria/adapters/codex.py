from __future__ import annotations

import subprocess
from dataclasses import dataclass
from types import MappingProxyType

from factoria.domain.models import CheckResult

from .argument_policy import AdapterArgumentPolicy
from .base import AgentRequest, AgentResult, SubprocessToolAdapter, ToolCapability


_CODEX_RESERVED_FLAGS = frozenset(
    {
        "--model",
        "-m",
        "--json",
        "--cd",
        "-C",
        "--full-auto",
        "--dangerously-bypass-approvals-and-sandbox",
    }
)


@dataclass(frozen=True, slots=True)
class CodexAdapter(SubprocessToolAdapter):
    executable: str = "codex"

    @property
    def name(self) -> str:
        return "codex"

    def capabilities(self) -> frozenset[ToolCapability]:
        return frozenset(
            {
                ToolCapability.NON_INTERACTIVE,
                ToolCapability.STRUCTURED_OUTPUT,
                ToolCapability.MODEL_SELECTION,
                ToolCapability.PROJECT_DIRECTORY,
                ToolCapability.READ_ONLY_ENFORCEMENT,
            }
        )

    def argument_policy(self) -> AdapterArgumentPolicy:
        # Only the exact safety flags Factoria currently needs are accepted.
        # Model, directory, output format and bypass flags remain Factoria-owned.
        return AdapterArgumentPolicy(
            allowed=MappingProxyType(
                {
                    "--sandbox": ("read-only",),
                    "--ask-for-approval": ("never",),
                }
            ),
            reserved=_CODEX_RESERVED_FLAGS,
        )

    def build_command(self, request: AgentRequest) -> tuple[str, ...]:
        args: list[str] = [self.executable]
        args.extend(self._validated_extra_args(request))
        args.append("exec")
        if request.structured_output:
            args.append("--json")
        if request.model:
            args.extend(["--model", request.model])
        args.append(request.prompt)
        return tuple(args)

    def run(self, request: AgentRequest) -> AgentResult:
        return self._execute(request, self.build_command(request), adapter_name=self.name)

    def _read_only_contract_check(self) -> CheckResult:
        """Probe Codex's parser without starting an agent execution.

        This verifies that the installed CLI accepts the exact restricted contract
        Factoria relies on. It intentionally does not claim to empirically test the
        underlying OS sandbox, which would require executing agent work.
        """
        if not self.available():
            return CheckResult(
                name="codex:safety:read_only_contract",
                passed=False,
                required=True,
                details=f"Executable not found: {self.executable}",
            )
        command = [
            self.executable,
            "--sandbox",
            "read-only",
            "--ask-for-approval",
            "never",
            "exec",
            "--help",
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return CheckResult(
                name="codex:safety:read_only_contract",
                passed=False,
                required=True,
                details=str(exc),
            )
        output = (completed.stdout or "") + "\n" + (completed.stderr or "")
        sanitized, findings = self.secret_scanner.redact(output)
        if findings:
            return CheckResult(
                name="codex:safety:read_only_contract",
                passed=False,
                required=True,
                details="Potential secret detected in Codex safety probe output; value redacted",
            )
        return CheckResult(
            name="codex:safety:read_only_contract",
            passed=completed.returncode == 0,
            required=True,
            details=(
                "restricted CLI contract accepted; OS sandbox enforcement is delegated to Codex"
                if completed.returncode == 0
                else sanitized[-500:] or f"exit={completed.returncode}"
            ),
        )

    def self_test(self) -> tuple[CheckResult, ...]:
        return (
            self._version_check(adapter_name=self.name),
            self._help_capability_check(
                adapter_name=self.name,
                args=("exec", "--help"),
                required_tokens=("--json", "--model"),
            ),
            self._read_only_contract_check(),
        )
