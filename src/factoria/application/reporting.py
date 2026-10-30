from __future__ import annotations

from dataclasses import dataclass

from factoria.application.fix_flow import FixRun
from factoria.domain.fix import FindingSeverity


@dataclass(frozen=True, slots=True)
class FixReportRenderer:
    """Render a stable human-readable report with fixed section ordering."""

    def render(self, run: FixRun) -> str:
        reproduction = run.reproduction
        scope = run.scope
        review = run.review

        lines = [
            "# Fix report",
            "",
            "## Summary",
            f"- Task: {run.task.title}",
            f"- Phase: {run.phase.value}",
            f"- Large fix: {'yes' if run.promoted_to_large else 'no'}",
            "",
            "## Reproduction",
        ]

        if reproduction is None:
            lines.append("- Not recorded")
        else:
            lines.append(f"- Type: {reproduction.kind.value}")
            lines.append(f"- Evidence: {reproduction.description}")

        lines.extend(["", "## Changes"])
        if scope is None:
            lines.append("- Scope not recorded")
        else:
            lines.append(f"- Files changed: {scope.files_changed}")
            lines.append(f"- Lines changed: {scope.lines_changed}")

        lines.extend(["", "## Verification"])
        if not run.verification:
            lines.append("- No verification results recorded")
        else:
            for result in run.verification:
                requirement = "required" if result.required else "optional"
                outcome = "passed" if result.passed else "failed"
                lines.append(f"- {result.name}: {outcome} ({requirement})")

        lines.extend(["", "## Review"])
        if review is None:
            lines.append("- No review recorded")
        else:
            counts = {
                severity: sum(1 for finding in review.findings if finding.severity is severity)
                for severity in FindingSeverity
            }
            lines.append(
                "- Findings: "
                f"critical={counts[FindingSeverity.CRITICAL]}, "
                f"important={counts[FindingSeverity.IMPORTANT]}, "
                f"minor={counts[FindingSeverity.MINOR]}"
            )
            lines.append(
                f"- Acceptance criteria met: {'yes' if review.acceptance_criteria_met else 'no'}"
            )
            if review.mandatory_rules_violated:
                lines.append(
                    "- Mandatory rules violated: " + ", ".join(review.mandatory_rules_violated)
                )

        lines.extend(
            [
                "",
                "## Decisions",
                f"- Review cycles used: {run.review_cycle}",
                "",
                "## Permissions",
                "- Not recorded by fix domain; supplied by execution context.",
                "",
                "## Final status",
                f"- Result: {run.phase.value}",
            ]
        )
        if run.block_reason:
            lines.append(f"- Block reason: {run.block_reason}")
        return "\n".join(lines) + "\n"
