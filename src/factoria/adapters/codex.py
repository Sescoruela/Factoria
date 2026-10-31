from __future__ import annotations

from dataclasses import dataclass

from factoria.domain.models import CheckResult

from .base import AgentRequest, AgentResult, SubprocessToolAdapter, ToolCapability


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
            }
        )

    def build_command(self, request: AgentRequest) -> tuple[str, ...]:
        args: list[str] = [self.executable]
        args.extend(request.extra_args)
        args.append("exec")
        if request.structured_output:
            args.append("--json")
        if request.model:
            args.extend(["--model", request.model])
        args.append(request.prompt)
        return tuple(args)

    def run(self, request: AgentRequest) -> AgentResult:
        return self._execute(request, self.build_command(request), adapter_name=self.name)

    def self_test(self) -> tuple[CheckResult, ...]:
        return (self._version_check(adapter_name=self.name),)
