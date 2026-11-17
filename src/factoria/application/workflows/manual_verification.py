from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from factoria.domain.models import ProjectMemory


@dataclass(frozen=True, slots=True)
class ManualVerificationRequirement:
    required: bool
    available: bool
    steps: tuple[str, ...] = ()
    reason: str | None = None


def inspect_manual_verification(
    workspace: Path,
    memory: ProjectMemory,
) -> ManualVerificationRequirement:
    verification = workspace / "verification.md"
    if not verification.exists():
        return ManualVerificationRequirement(
            required=True,
            available=False,
            reason="Verification evidence is missing",
        )

    text = verification.read_text(encoding="utf-8", errors="replace")
    automated = any(
        line.startswith("- PASS ") or line.startswith("- FAIL ") for line in text.splitlines()
    )
    if automated:
        return ManualVerificationRequirement(required=False, available=True)

    if "No confirmed automated checks selected." not in text:
        return ManualVerificationRequirement(
            required=True,
            available=False,
            reason="Verification evidence does not identify an automated or manual path",
        )

    steps = tuple(item.strip() for item in memory.manual_verification if item.strip())
    if not steps:
        return ManualVerificationRequirement(
            required=True,
            available=False,
            reason="No confirmed automated checks or manual verification steps are available",
        )

    return ManualVerificationRequirement(
        required=True,
        available=True,
        steps=steps,
        reason="No confirmed automated checks were selected",
    )


def record_manual_verification(
    workspace: Path,
    requirement: ManualVerificationRequirement,
) -> Path:
    if not requirement.required or not requirement.available:
        raise ValueError("Manual verification confirmation is not applicable")
    path = workspace / "manual-verification.json"
    path.write_text(
        json.dumps(
            {
                "confirmed": True,
                "confirmed_at": datetime.now(timezone.utc).isoformat(),
                "steps": list(requirement.steps),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path
