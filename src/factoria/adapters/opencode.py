from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from factoria.domain.models import CheckResult

from .base import AgentRequest, AgentResult, SubprocessToolAdapter, ToolCapability


_READ_ONLY_PERMISSION = {
    "*": "deny",
    "read": "allow",
    "glob": "allow",
    "grep": "allow",
    "lsp": "allow",
}
_IMPLEMENTER_PERMISSION = {
    "*": "deny",
    "read": "allow",
    "glob": "allow",
    "grep": "allow",
    "lsp": "allow",
    "edit": "allow",
}


def opencode_read_only_config_content() -> str:
    return json.dumps({"permission": _READ_ONLY_PERMISSION}, separators=(",", ":"))


def opencode_implementer_config_content() -> str:
    return json.dumps({"permission": _IMPLEMENTER_PERMISSION}, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class OpenCodeAdapter(SubprocessToolAdapter):
    executable: str = "opencode"

    @property
    def name(self) -> str:
        return "opencode"

    def capabilities(self) -> frozenset[ToolCapability]:
        return frozenset(
            {
                ToolCapability.NON_INTERACTIVE,
                ToolCapability.STRUCTURED_OUTPUT,
                ToolCapability.MODEL_SELECTION,
                ToolCapability.PROJECT_DIRECTORY,
                ToolCapability.READ_ONLY_ENFORCEMENT,
                ToolCapability.PROJECT_WRITE_ENFORCEMENT,
            }
        )

    def build_command(self, request: AgentRequest) -> tuple[str, ...]:
        args: list[str] = [self.executable, "run", "--dir", str(request.project_root)]
        if request.structured_output:
            args.extend(["--format", "json"])
        if request.model:
            args.extend(["--model", request.model])
        # Permissions are provided through OPENCODE_CONFIG_CONTENT, which is a
        # documented runtime configuration layer with higher precedence than
        # project config. No orchestration-supplied CLI arguments are approved.
        args.extend(self._validated_extra_args(request))
        args.append(request.prompt)
        return tuple(args)

    def run(self, request: AgentRequest) -> AgentResult:
        return self._execute(request, self.build_command(request), adapter_name=self.name)

    def _resolved_permission_check(
        self,
        *,
        name: str,
        config_content: str,
        expected: dict[str, str],
    ) -> CheckResult:
        """Verify OpenCode's resolved config without starting an agent.

        The temporary project deliberately contains permissive project config.
        The probe succeeds only when the documented inline runtime config wins and
        the resolved permission object still contains Factoria's restrictive
        contract.
        """
        if not self.available():
            return CheckResult(
                name=name,
                passed=False,
                required=True,
                details=f"Executable not found: {self.executable}",
            )
        environment = os.environ.copy()
        environment["OPENCODE_CONFIG_CONTENT"] = config_content
        try:
            with tempfile.TemporaryDirectory(prefix="factoria-opencode-probe-") as temp_dir:
                root = Path(temp_dir)
                (root / "opencode.json").write_text(
                    json.dumps({"permission": "allow"}),
                    encoding="utf-8",
                )
                completed = subprocess.run(
                    [self.executable, "debug", "config"],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                    timeout=10,
                    env=environment,
                )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return CheckResult(name=name, passed=False, required=True, details=str(exc))

        output = completed.stdout or completed.stderr or ""
        sanitized, findings = self.secret_scanner.redact(output)
        if findings:
            return CheckResult(
                name=name,
                passed=False,
                required=True,
                details="Potential secret detected in OpenCode config probe output; value redacted",
            )
        if completed.returncode != 0:
            return CheckResult(
                name=name,
                passed=False,
                required=True,
                details=sanitized[-500:] or f"exit={completed.returncode}",
            )
        try:
            resolved = json.loads(completed.stdout)
        except (json.JSONDecodeError, TypeError) as exc:
            return CheckResult(
                name=name,
                passed=False,
                required=True,
                details=f"OpenCode debug config did not return JSON: {exc}",
            )
        permissions = resolved.get("permission")
        if not isinstance(permissions, dict):
            return CheckResult(
                name=name,
                passed=False,
                required=True,
                details="Resolved OpenCode config does not expose a permission object",
            )
        mismatches = [
            f"{key}={permissions.get(key)!r} expected {value!r}"
            for key, value in expected.items()
            if permissions.get(key) != value
        ]
        return CheckResult(
            name=name,
            passed=not mismatches,
            required=True,
            details=(
                "resolved runtime permission contract verified"
                if not mismatches
                else "permission mismatch: " + "; ".join(mismatches)
            ),
        )

    def self_test(self) -> tuple[CheckResult, ...]:
        return (
            self._version_check(adapter_name=self.name),
            self._help_capability_check(
                adapter_name=self.name,
                args=("run", "--help"),
                required_tokens=("--dir", "--format", "--model"),
            ),
            self._resolved_permission_check(
                name="opencode:safety:read_only_contract",
                config_content=opencode_read_only_config_content(),
                expected=_READ_ONLY_PERMISSION,
            ),
            self._resolved_permission_check(
                name="opencode:safety:project_write_contract",
                config_content=opencode_implementer_config_content(),
                expected=_IMPLEMENTER_PERMISSION,
            ),
        )
