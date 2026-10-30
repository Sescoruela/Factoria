from __future__ import annotations

import unittest

from factoria.application.quality import (
    CheckPlanner,
    CheckSpec,
    ReviewAction,
    ReviewGate,
    VerificationGate,
)
from factoria.domain.fix import (
    FindingSeverity,
    ReviewFinding,
    ReviewResult,
    VerificationResult,
)
from factoria.domain.models import ModuleMemory, ProjectMemory


class QualityTests(unittest.TestCase):
    def test_required_verification_failure_blocks_gate(self) -> None:
        decision = VerificationGate.evaluate(
            (
                VerificationResult("unit", passed=True, required=True),
                VerificationResult("lint", passed=False, required=False),
                VerificationResult("build", passed=False, required=True),
            )
        )

        self.assertFalse(decision.passed)
        self.assertEqual(tuple(item.name for item in decision.failed_required), ("build",))

    def test_review_gate_retries_then_blocks(self) -> None:
        review = ReviewResult(
            findings=(ReviewFinding(FindingSeverity.IMPORTANT, "Needs correction"),)
        )
        gate = ReviewGate(max_cycles=2)

        first = gate.evaluate(review, current_cycle=0)
        second = gate.evaluate(review, current_cycle=1)
        third = gate.evaluate(review, current_cycle=2)

        self.assertEqual(first.action, ReviewAction.CORRECT)
        self.assertEqual(second.action, ReviewAction.CORRECT)
        self.assertEqual(third.action, ReviewAction.BLOCK)

    def test_check_planner_selects_affected_and_global_checks(self) -> None:
        memory = ProjectMemory(
            project_name="demo",
            modules=(
                ModuleMemory(name="frontend", paths=("frontend",), affects=("shared",)),
                ModuleMemory(name="backend", paths=("backend",)),
                ModuleMemory(name="shared", paths=("shared",)),
            ),
        )
        checks = (
            CheckSpec("frontend-test", "test", scope="frontend", required=True),
            CheckSpec("backend-test", "test", scope="backend", required=True),
            CheckSpec("shared-typecheck", "typecheck", scope="shared", required=True),
            CheckSpec("repo-smoke", "smoke", required=True, global_check=True),
        )

        plan = CheckPlanner(memory).plan(("frontend/src/app.ts",), checks)

        self.assertEqual(plan.affected_modules, ("frontend", "shared"))
        self.assertEqual(
            tuple(check.name for check in plan.checks),
            ("frontend-test", "shared-typecheck", "repo-smoke"),
        )


if __name__ == "__main__":
    unittest.main()
