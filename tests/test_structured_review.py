from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from factoria.adapters.base import AgentResult
from factoria.application.agent_flow_runtime import LiveAgentFlowRunner, LiveFlowSession
from factoria.application.artifacts import FlowArtifactStore
from factoria.application.review_runtime import ReviewParseError, parse_structured_review
from factoria.domain.models import ProjectMemory
from factoria.orchestration import AgentRole, AgentWorkflowPlanner, ModelProfile
from factoria.orchestration.models import AgentAttemptTrace, AgentStageTrace
from factoria.orchestration.orchestrator import AgentStageResult


class StructuredReviewParserTests(unittest.TestCase):
    def test_important_finding_requires_changes(self) -> None:
        payload = json.dumps(
            {
                "result": "changes_required",
                "acceptance_criteria_met": True,
                "mandatory_rules_violated": [],
                "findings": [
                    {"severity": "important", "message": "Handle the error path", "rule": None}
                ],
                "risks": ["Regression on failure path"],
                "recommendation": "Correct the finding and review again",
            }
        )
        review = parse_structured_review(payload)
        self.assertTrue(review.blocks_closure)
        self.assertEqual(review.review.blocking_findings[0].severity.value, "important")

    def test_minor_only_review_can_be_approved(self) -> None:
        payload = json.dumps(
            {
                "result": "approved",
                "acceptance_criteria_met": True,
                "mandatory_rules_violated": [],
                "findings": [
                    {"severity": "minor", "message": "Consider a clearer local name", "rule": None}
                ],
                "risks": [],
                "recommendation": "Accept",
            }
        )
        review = parse_structured_review(payload)
        self.assertFalse(review.blocks_closure)

    def test_contradictory_result_is_rejected(self) -> None:
        payload = json.dumps(
            {
                "result": "approved",
                "acceptance_criteria_met": False,
                "mandatory_rules_violated": [],
                "findings": [],
                "risks": [],
                "recommendation": "Accept",
            }
        )
        with self.assertRaises(ReviewParseError):
            parse_structured_review(payload)


class _FakeOrchestrator:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs
        self.roles: list[AgentRole] = []

    def run(self, stage, *, project_root: Path) -> AgentStageResult:
        self.roles.append(stage.role)
        output = self.outputs.pop(0)
        attempt = AgentAttemptTrace(
            attempt=1,
            role=stage.role,
            adapter="fake",
            profile=stage.profile or ModelProfile.POTENTE,
            model=None,
            fallback=False,
            passed=True,
        )
        return AgentStageResult(
            result=AgentResult(
                adapter="fake",
                command=(),
                returncode=0,
                stdout=output,
            ),
            trace=AgentStageTrace(stage.role, (attempt,)),
        )


class _ReviewRunner(LiveAgentFlowRunner):
    def _verify(self, project_root: Path, memory: ProjectMemory, flow_id: str) -> bool:
        self.artifacts.write_text(flow_id, "verification.md", "# Verification\n\n- PASS fake\n")
        return True


class StructuredReviewLoopTests(unittest.TestCase):
    def test_blocking_review_triggers_correction_then_rereview(self) -> None:
        first = json.dumps(
            {
                "result": "changes_required",
                "acceptance_criteria_met": True,
                "mandatory_rules_violated": [],
                "findings": [
                    {"severity": "important", "message": "Fix the branch condition", "rule": None}
                ],
                "risks": [],
                "recommendation": "Correct and review again",
            }
        )
        approved = json.dumps(
            {
                "result": "approved",
                "acceptance_criteria_met": True,
                "mandatory_rules_violated": [],
                "findings": [],
                "risks": [],
                "recommendation": "Accept",
            }
        )
        fake = _FakeOrchestrator([first, "correction applied", approved])
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifacts = FlowArtifactStore(root)
            runner = _ReviewRunner(
                service=None,  # type: ignore[arg-type]
                store=None,  # type: ignore[arg-type]
                artifacts=artifacts,
                orchestrator=fake,  # type: ignore[arg-type]
                check_executor=None,  # type: ignore[arg-type]
            )
            session = LiveFlowSession(
                flow_id="flow-1",
                kind="fix",
                title="Fix condition",
                branch="work",
                preferred_tool=None,
                phase="running",
            )
            reviewer = next(
                step
                for step in AgentWorkflowPlanner.fix(large=False, update_memory=False).steps
                if step.role is AgentRole.REVIEWER
            )
            execution = object()
            returned, accepted = runner._run_review_with_corrections(
                execution,  # type: ignore[arg-type]
                session,
                reviewer_step=reviewer,
                project_root=root,
                memory=ProjectMemory(project_name="demo"),
            )
            self.assertIs(returned, execution)
            self.assertTrue(accepted)
            self.assertEqual(
                fake.roles,
                [AgentRole.REVIEWER, AgentRole.IMPLEMENTER, AgentRole.REVIEWER],
            )
            workspace = artifacts.workspace("flow-1").root
            self.assertTrue((workspace / "review-cycle-0.json").exists())
            self.assertTrue((workspace / "correction-1.txt").exists())
            self.assertTrue((workspace / "review-cycle-1.json").exists())


if __name__ == "__main__":
    unittest.main()
