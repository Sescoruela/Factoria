from __future__ import annotations

import subprocess
from dataclasses import dataclass
from types import MappingProxyType

from factoria.domain.models import CheckResult

from .argument_policy import AdapterArgumentPolicy
from .base import AgentRequest, AgentResult, SubprocessToolAdapter, ToolCapability
from .codex_discovery import discover_codex


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

    def _resolved_executable(self) -> str | None:
        discovery = discover_codex()
        return str(discovery.cli_path) if discovery.cli_path is not None else None

    def available(self) -> bool:
        return self._resolved_executable() is not None

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
        executable = self._resolved_executable() or self.executable
        args: list[str] = [executable]
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

    def _run_probe(
        self, args: tuple[str, ...], *, name: str, required_tokens: tuple[str, ...] = ()
    ) -> CheckResult:
        executable = self._resolved_executable()
        if executable is None:
            discovery = discover_codex()
            details = "Codex CLI no encontrado."
            if discovery.desktop_detected:
                details += (
                    " ChatGPT Desktop con Codex parece estar instalado, pero Factoria no ejecuta "
                    "binarios internos de la app; configura CODEX_CLI_PATH o instala/expón Codex CLI."
                )
            return CheckResult(name=name, passed=False, required=True, details=details)
        try:
            completed = subprocess.run(
                [executable, *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return CheckResult(name=name, passed=False, required=True, details=str(exc))
        output = (completed.stdout or "") + "\n" + (completed.stderr or "")
        sanitized, findings = self.secret_scanner.redact(output)
        if findings:
            return CheckResult(
                name=name,
                passed=False,
                required=True,
                details="Potential secret detected in Codex probe output; value redacted",
            )
        missing = tuple(token for token in required_tokens if token not in sanitized)
        passed = completed.returncode == 0 and not missing
        if passed:
            details = "supported"
        elif missing:
            details = "missing expected CLI flags: " + ", ".join(missing)
        else:
            details = sanitized[-500:] or f"exit={completed.returncode}"
        return CheckResult(name=name, passed=passed, required=True, details=details)

    def _read_only_contract_check(self) -> CheckResult:
        executable = self._resolved_executable()
        if executable is None:
            discovery = discover_codex()
            details = "Codex CLI no encontrado."
            if discovery.desktop_detected:
                details += " Codex está presente en ChatGPT Desktop, pero esa integración no expone una CLI pública documentada para Factoria."
            return CheckResult(
                name="codex:safety:read_only_contract",
                passed=False,
                required=True,
                details=details,
            )
        command = [
            executable,
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
            self._run_probe(("--version",), name="codex:installed"),
            self._run_probe(
                ("exec", "--help"),
                name="codex:capabilities",
                required_tokens=("--json", "--model"),
            ),
            self._read_only_contract_check(),
        )
