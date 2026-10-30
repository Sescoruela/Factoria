import unittest

from factoria.application.feature_flow import FeatureFlowError, FeatureRun
from factoria.domain.feature import AcceptanceCriterion, FeatureOutcome, FeaturePlan, FeatureTask, FeaturePhase
from factoria.domain.fix import FindingSeverity, ReviewFinding, ReviewResult, VerificationResult


class FeatureFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.task = FeatureTask(
            task_id="feature-1",
            title="Add project status",
            description="Expose project status from the factory",
            acceptance_criteria=(
                AcceptanceCriterion("Status can be requested"),
                AcceptanceCriterion("Output remains stable", functional=False),
            ),
        )
        self.plan = FeaturePlan(summary="Add status service", steps=("model", "service", "tests"))

    def test_feature_requires_plan_approval_before_implementation(self) -> None:
        run = FeatureRun(self.task).propose_plan(self.plan)
        self.assertEqual(run.phase, FeaturePhase.AWAITING_PLAN_APPROVAL)
        run = run.approve_plan()
        self.assertEqual(run.phase, FeaturePhase.IMPLEMENT)

    def test_required_verification_failure_blocks_feature(self) -> None:
        run = FeatureRun(self.task).propose_plan(self.plan).approve_plan()
        outcome = FeatureOutcome(
            verifications=(VerificationResult("tests", False, True),),
        )
        self.assertEqual(run.record_outcome(outcome).phase, FeaturePhase.BLOCKED)

    def test_blocking_review_finding_blocks_feature(self) -> None:
        run = FeatureRun(self.task).propose_plan(self.plan).approve_plan()
        outcome = FeatureOutcome(
            verifications=(VerificationResult("tests", True, True),),
            review=ReviewResult(findings=(ReviewFinding(FindingSeverity.IMPORTANT, "missing case"),)),
        )
        self.assertEqual(run.record_outcome(outcome).phase, FeaturePhase.BLOCKED)

    def test_memory_update_and_final_approval_are_explicit_gates(self) -> None:
        run = FeatureRun(self.task).propose_plan(self.plan).approve_plan()
        outcome = FeatureOutcome(
            verifications=(VerificationResult("tests", True, True),),
            memory_update_required=True,
        )
        run = run.record_outcome(outcome)
        self.assertEqual(run.phase, FeaturePhase.MEMORY_UPDATE)
        run = run.confirm_memory_update()
        self.assertEqual(run.phase, FeaturePhase.AWAITING_FINAL_APPROVAL)
        run = run.approve_final()
        self.assertEqual(run.phase, FeaturePhase.COMPLETED)

    def test_feature_without_acceptance_criteria_cannot_be_planned(self) -> None:
        task = FeatureTask("f", "title", "description")
        with self.assertRaises(FeatureFlowError):
            FeatureRun(task).propose_plan(self.plan)


if __name__ == "__main__":
    unittest.main()
