import unittest

from factoria.application.fix_flow import FixRun
from factoria.application.reporting import FixReportRenderer
from factoria.domain.fix import (
    ChangeScope,
    FixTask,
    ReproductionEvidence,
    ReproductionKind,
    ReviewResult,
    VerificationResult,
)


class FixReportTests(unittest.TestCase):
    def test_report_uses_stable_section_order(self) -> None:
        run = FixRun(FixTask("fix-1", "Bug", "Description"))
        run = run.record_reproduction(ReproductionEvidence(ReproductionKind.MANUAL, "Steps"))
        run = run.assess_scope(ChangeScope(1, 3)).implementation_completed()
        run = run.record_verification((VerificationResult("manual", True, True),))
        run = run.record_review(ReviewResult())

        report = FixReportRenderer().render(run)
        sections = [
            "## Summary",
            "## Reproduction",
            "## Changes",
            "## Verification",
            "## Review",
            "## Decisions",
            "## Permissions",
            "## Final status",
        ]
        positions = [report.index(section) for section in sections]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("manual: passed (required)", report)


if __name__ == "__main__":
    unittest.main()
