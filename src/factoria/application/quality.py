from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PurePosixPath

from factoria.domain.fix import ReviewResult, VerificationResult
from factoria.domain.models import ModuleMemory, ProjectMemory


@dataclass(frozen=True, slots=True)
class VerificationDecision:
    passed: bool
    failed_required: tuple[VerificationResult, ...] = field(default_factory=tuple)

    @property
    def reason(self) -> str | None:
        if not self.failed_required:
            return None
        names = ", ".join(result.name for result in self.failed_required)
        return f"Required verification failed: {names}"


class VerificationGate:
    @staticmethod
    def evaluate(results: tuple[VerificationResult, ...]) -> VerificationDecision:
        failed = tuple(result for result in results if result.required and not result.passed)
        return VerificationDecision(passed=not failed, failed_required=failed)


class ReviewAction(StrEnum):
    ACCEPT = "accept"
    CORRECT = "correct"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class ReviewDecision:
    action: ReviewAction
    next_cycle: int
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ReviewGate:
    max_cycles: int = 2

    def evaluate(self, review: ReviewResult, *, current_cycle: int) -> ReviewDecision:
        next_cycle = current_cycle + 1
        if not review.blocks_closure:
            return ReviewDecision(ReviewAction.ACCEPT, next_cycle)
        if next_cycle <= self.max_cycles:
            return ReviewDecision(ReviewAction.CORRECT, next_cycle)
        return ReviewDecision(
            ReviewAction.BLOCK,
            next_cycle,
            "Blocking review findings remain after configured correction cycles",
        )


@dataclass(frozen=True, slots=True)
class CheckSpec:
    name: str
    category: str
    scope: str | None = None
    required: bool = True
    global_check: bool = False


@dataclass(frozen=True, slots=True)
class CheckPlan:
    affected_modules: tuple[str, ...]
    checks: tuple[CheckSpec, ...]


@dataclass(frozen=True, slots=True)
class CheckPlanner:
    memory: ProjectMemory

    def plan(
        self,
        changed_files: tuple[str, ...],
        available_checks: tuple[CheckSpec, ...],
    ) -> CheckPlan:
        affected = self._affected_modules(changed_files)
        selected = tuple(
            check
            for check in available_checks
            if check.global_check or check.scope is None or check.scope in affected
        )
        return CheckPlan(affected_modules=affected, checks=selected)

    def _affected_modules(self, changed_files: tuple[str, ...]) -> tuple[str, ...]:
        direct = {
            module.name
            for module in self.memory.modules
            if any(self._matches(module, file_path) for file_path in changed_files)
        }
        expanded = set(direct)
        changed = True
        while changed:
            changed = False
            for module in self.memory.modules:
                if module.name in expanded:
                    for related in module.affects:
                        if related not in expanded:
                            expanded.add(related)
                            changed = True
        order = [module.name for module in self.memory.modules if module.name in expanded]
        return tuple(order)

    @staticmethod
    def _matches(module: ModuleMemory, file_path: str) -> bool:
        normalized = str(PurePosixPath(file_path.replace("\\", "/")))
        for raw in module.paths:
            prefix = str(PurePosixPath(raw.replace("\\", "/"))).rstrip("/")
            if normalized == prefix or normalized.startswith(prefix + "/"):
                return True
        return False
