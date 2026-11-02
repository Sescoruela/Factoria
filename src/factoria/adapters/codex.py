from __future__ import annotations

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

    def self_test(self) -> tuple[CheckResult, ...]:
        return (
            self._version_check(adapter_name=self.name),
            self._help_capability_check(
                adapter_name=self.name,
                args=("exec", "--help"),
                required_tokens=("--json", "--model"),
            ),
        )
