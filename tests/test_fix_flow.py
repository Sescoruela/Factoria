import unittest

from factoria.application.fix_flow import FixFlowError, FixRun
from factoria.domain.fix import (
    ChangeScope,
    FindingSeverity,
    FixLimits,
    FixPhase,
    FixTask,
    ReproductionEvidence,
    ReproductionKind,
    ReviewFinding,
    ReviewResult,
    VerificationResult,
)


class FixFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.task = FixTask(
            task_id="fix-1",
            title="Correct invoice total",
            description="Invoice total is wrong when a discount is applied",
            acceptance_criteria=("Discounted total is correct",),
        )

    def test_small_fix_can_complete_without_approval_gate(self) -> None:
        run = FixRun(task=self.task)
        run = run.record_reproduction(
            ReproductionEvidence(ReproductionKind.MANUAL, "Create invoice with 10% discount")
        )
        run = run.assess_scope(ChangeScope(files_changed=2, lines_changed=40))
        run = run.implementation_completed()
        run = run.record_verification(
            (VerificationResult("manual reproduction", passed=True, required=True),)
        )
        run = run.record_review(ReviewResult())

        self.assertEqual(run.phase, FixPhase.COMPLETED)
        self.assertFalse(run.promoted_to_large)

    def test_large_fix_requires_plan_and_final_approval(self) -> None:
        run = FixRun(task=self.task, limits=FixLimits(max_files=2, max_changed_lines=30))
        run = run.record_reproduction(
            ReproductionEvidence(ReproductionKind.SCRIPT, "Run reproduction.py")
        )
        run = run.assess_scope(ChangeScope(files_changed=3, lines_changed=20))

        self.assertEqual(run.phase, FixPhase.AWAITING_PLAN_APPROVAL)
        run = run.approve_large_plan().implementation_completed()
        run = run.record_verification((VerificationResult("smoke", True, True),))
        run = run.record_review(ReviewResult())
        self.assertEqual(run.phase, FixPhase.AWAITING_FINAL_APPROVAL)
        self.assertEqual(run.approve_final().phase, FixPhase.COMPLETED)

    def test_required_verification_failure_blocks(self) -> None:
        run = FixRun(task=self.task)
        run = run.record_reproduction(
            ReproductionEvidence(ReproductionKind.AUTOMATED_TEST, "Regression test fails")
        )
        run = run.assess_scope(ChangeScope(1, 5)).implementation_completed()
        run = run.record_verification((VerificationResult("tests", False, True, "1 failed"),))

        self.assertEqual(run.phase, FixPhase.BLOCKED)
        self.assertIn("tests", run.block_reason or "")

    def test_blocking_review_retries_then_blocks(self) -> None:
        finding = ReviewFinding(FindingSeverity.IMPORTANT, "Acceptance behavior incomplete")
        result = ReviewResult(findings=(finding,))
        run = FixRun(task=self.task, limits=FixLimits(max_review_cycles=1))
        run = run.record_reproduction(ReproductionEvidence(ReproductionKind.MANUAL, "Steps"))
        run = run.assess_scope(ChangeScope(1, 10)).implementation_completed()
        run = run.record_verification((VerificationResult("manual", True, True),))
        run = run.record_review(result)
        self.assertEqual(run.phase, FixPhase.CORRECTION)

        run = run.implementation_completed()
        run = run.record_verification((VerificationResult("manual", True, True),))
        run = run.record_review(result)
        self.assertEqual(run.phase, FixPhase.BLOCKED)

    def test_reproduction_is_required_before_scope_analysis(self) -> None:
        with self.assertRaises(FixFlowError):
            FixRun(task=self.task).assess_scope(ChangeScope(1, 1))


if __name__ == "__main__":
    unittest.main()
