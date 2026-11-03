from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType

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
_DEFAULT_OPENCODE_TIMEOUT_SECONDS = 600


def opencode_read_only_config_content() -> str:
    return json.dumps({"permission": _READ_ONLY_PERMISSION}, separators=(",", ":"))


def opencode_implementer_config_content() -> str:
    return json.dumps({"permission": _IMPLEMENTER_PERMISSION}, separators=(",", ":"))


def _opencode_timeout_seconds(requested: int) -> int:
    raw = os.environ.get("FACTORIA_OPENCODE_TIMEOUT_SECONDS", "").strip()
    if raw:
        try:
            configured = int(raw)
        except ValueError:
            configured = _DEFAULT_OPENCODE_TIMEOUT_SECONDS
        configured = max(30, min(configured, 3600))
    else:
        configured = _DEFAULT_OPENCODE_TIMEOUT_SECONDS
    return min(requested, configured)


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
        args.extend(self._validated_extra_args(request))
        args.append(request.prompt)
        return tuple(args)

    def run(self, request: AgentRequest) -> AgentResult:
        environment = dict(request.environment)
        permission = environment.pop("OPENCODE_PERMISSION", None)
        if permission is not None:
            try:
                parsed = json.loads(permission)
            except json.JSONDecodeError as exc:
                return AgentResult(
                    adapter=self.name,
                    command=self.build_command(request),
                    returncode=None,
                    error=f"Invalid Factoria OpenCode permission policy: {exc}",
                )
            environment["OPENCODE_CONFIG_CONTENT"] = json.dumps(
                {"permission": parsed}, separators=(",", ":")
            )
        effective_request = replace(
            request,
            environment=MappingProxyType(environment),
            timeout_seconds=_opencode_timeout_seconds(request.timeout_seconds),
        )
        return self._execute(
            effective_request,
            self.build_command(effective_request),
            adapter_name=self.name,
        )

    def _resolved_permission_check(
        self,
        *,
        name: str,
        config_content: str,
        expected: dict[str, str],
    ) -> CheckResult:
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
