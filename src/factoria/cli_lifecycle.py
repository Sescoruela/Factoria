from __future__ import annotations

import json
from pathlib import Path

from .application.agent_flow_runtime import build_live_runner
from .application.git_lifecycle import GitLifecycle
from .application.governance import ExecutionGovernor, GovernedAction
from .application.history import LocalExecutionHistoryStore
from .application.impact import ImpactAnalyzer
from .application.manual_verification import (
    inspect_manual_verification,
    record_manual_verification,
)
from .application.policy_runtime import build_execution_context
from .domain.permissions import PermissionProfile
from .memory.loader import load_project_memory


def register_lifecycle_commands(sub) -> None:
    commit = sub.add_parser("commit", help="Preview and explicitly commit an approved flow")
    commit.add_argument("flow_id", nargs="?")
    commit.add_argument("--message", help="Override the proposed commit message")
    commit.add_argument("--yes", action="store_true", help="Confirm staging and creating the commit")
    commit.add_argument(
        "--confirm-manual-verification",
        action="store_true",
        help="Confirm that all persisted manual verification steps were completed",
    )
    commit.add_argument(
        "--confirm-external-impact-review",
        action="store_true",
        help="Confirm manual review of declared external contract/dependency impact",
    )

    history = sub.add_parser("history", help="Show local execution history")
    history.add_argument("--kind", choices=("fix", "feature"))
    history.add_argument("--state", choices=("completed", "cancelled"))
    history.add_argument("--limit", type=int, default=20)
    history.add_argument("--flow-id", help="Show only one execution")
    history.add_argument(
        "--report",
        action="store_true",
        help="Render the full persisted final report for the selected execution",
    )


def archive_terminal(root: Path, execution, snapshot: dict[str, str]) -> None:
    if not execution.is_terminal:
        return
    git = GitLifecycle(root)
    LocalExecutionHistoryStore(root).archive(
        execution,
        artifacts=snapshot,
        branch=git.current_branch() or None,
        commit_sha=git.head_sha(),
    )


def run_commit(args, root: Path, execution) -> int:
    if args.read_only:
        raise PermissionError("--read-only forbids staging or committing changes")
    requested = PermissionProfile(args.profile) if getattr(args, "profile", None) else None
    context = build_execution_context(root, requested_profile=requested, flow_authorized=True)
    governor = ExecutionGovernor()
    governor.assert_allowed(GovernedAction.WRITE, context)
    governor.assert_allowed(GovernedAction.COMMAND, context)

    session_path = execution.workspace.root / "agent-flow.json"
    if not session_path.exists():
        raise RuntimeError("This flow does not have live-agent metadata")
    session = json.loads(session_path.read_text(encoding="utf-8"))
    if session.get("phase") != "ready_for_commit":
        raise RuntimeError(
            f"Flow is not ready for commit; current phase is {session.get('phase', 'unknown')}"
        )

    memory = load_project_memory(root)
    manual = inspect_manual_verification(execution.workspace.root, memory)
    if manual.required:
        if not manual.available:
            raise RuntimeError(manual.reason or "No valid verification path is available")
        print("Verificación manual requerida:")
        for step in manual.steps:
            print(f"- {step}")
        if not args.confirm_manual_verification:
            if args.yes:
                raise RuntimeError(
                    "Manual verification is required; repeat with --confirm-manual-verification only after completing every listed step"
                )
            print(
                "La verificación manual aún no está confirmada. "
                "Completa los pasos y usa --confirm-manual-verification al confirmar el commit."
            )

    lifecycle = GitLifecycle(root)
    proposal = lifecycle.prepare(execution, message=args.message)
    impact = ImpactAnalyzer().analyze(memory, tuple(change.path for change in proposal.changes))
    (execution.workspace.root / "impact.md").write_text(
        ImpactAnalyzer.render(impact), encoding="utf-8", newline=""
    )
    if impact.items:
        print("Impacto detectado:")
        for item in impact.items:
            print(f"- {item.kind}: {item.name} [{item.confidence}] {item.evidence}")
    if impact.blocking and not args.confirm_external_impact_review:
        message = (
            "External contract impact requires manual review; repeat with "
            "--confirm-external-impact-review only after checking the affected repository/consumer"
        )
        if args.yes:
            raise RuntimeError(message)
        print(message)

    print(f"Rama: {proposal.branch}")
    print("Archivos que se incluirán:")
    for change in proposal.changes:
        print(f"- {change.status} {change.path}")
    print(f"Mensaje propuesto: {proposal.message}")
    if not args.yes:
        print("Commit no ejecutado. Repite con --yes después de revisar archivos y mensaje.")
        return 0

    if impact.blocking and not args.confirm_external_impact_review:
        raise RuntimeError("External impact review confirmation is required before commit")

    if manual.required:
        if not args.confirm_manual_verification:
            raise RuntimeError("Manual verification confirmation is required before commit")
        record_manual_verification(execution.workspace.root, manual)

    result = lifecycle.commit(proposal, confirmed=True, message=args.message)
    (execution.workspace.root / "commit.json").write_text(
        json.dumps(
            {"sha": result.sha, "message": result.message, "files": list(result.files)},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    if impact.blocking:
        (execution.workspace.root / "external-impact-review.json").write_text(
            json.dumps(
                {
                    "confirmed": True,
                    "external_dependencies": [item.name for item in impact.external_impacts],
                    "contracts": [item.name for item in impact.contract_impacts],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    history = LocalExecutionHistoryStore(root)
    snapshot = history.snapshot(execution.workspace.root)
    updated = build_live_runner(root).resume(flow_id=execution.flow.flow_id, project_root=root)
    archive_terminal(root, updated, snapshot)
    print(f"Commit creado: {result.sha}")
    print(f"Mensaje: {result.message}")
    if manual.required:
        print("Verificación manual: confirmada y archivada.")
    if impact.blocking:
        print("Impacto externo: revisión manual confirmada y archivada.")
    print("Flujo cerrado. Push y PR siguen siendo manuales.")
    return 0


def run_history(args, root: Path) -> int:
    store = LocalExecutionHistoryStore(root)
    all_records = store.list(kind=args.kind, state=args.state)
    if args.flow_id:
        all_records = tuple(item for item in all_records if item.flow_id == args.flow_id)
    if args.report:
        if not args.flow_id:
            raise RuntimeError("--report requires --flow-id")
        if not all_records:
            raise RuntimeError(f"Execution not found in local history: {args.flow_id}")
        print(store.render_report(all_records[0]), end="")
        return 0

    visible = all_records[: max(0, args.limit)]
    completed = sum(item.state == "completed" for item in all_records)
    cancelled = sum(item.state == "cancelled" for item in all_records)
    durations = [item.duration_seconds for item in all_records if item.duration_seconds is not None]
    average = sum(durations) / len(durations) if durations else None
    attempts = sum(item.agent_attempts for item in all_records)
    fallbacks = sum(item.agent_fallbacks for item in all_records)
    print(f"Ejecuciones: {len(all_records)} | completadas: {completed} | canceladas: {cancelled}")
    if average is not None:
        print(f"Duración media: {average:.1f}s")
    print(f"Intentos de agente: {attempts} | fallbacks: {fallbacks}")
    for record in visible:
        duration = f"{record.duration_seconds:.1f}s" if record.duration_seconds is not None else "-"
        profile = record.permission_profile or "-"
        escalated = " escalated" if record.permission_escalated else ""
        adapters = ",".join(record.agent_adapters) or "-"
        models = ",".join(record.agent_models) or "-"
        print(
            f"- {record.flow_id} | {record.kind} | {record.state} | "
            f"{record.branch or '-'} | {duration} | profile={profile}{escalated} | "
            f"attempts={record.agent_attempts} fallbacks={record.agent_fallbacks} | "
            f"adapters={adapters} models={models} | {record.label or '-'}"
        )
    if not visible:
        print("Sin ejecuciones registradas")
    return 0
