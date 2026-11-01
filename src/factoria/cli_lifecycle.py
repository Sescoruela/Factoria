from __future__ import annotations

import json
from pathlib import Path

from .application.agent_flow_runtime import build_live_runner
from .application.git_lifecycle import GitLifecycle
from .application.governance import ExecutionGovernor, GovernedAction
from .application.history import LocalExecutionHistoryStore
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

    history = sub.add_parser("history", help="Show local execution history")
    history.add_argument("--kind", choices=("fix", "feature"))
    history.add_argument("--state", choices=("completed", "cancelled"))
    history.add_argument("--limit", type=int, default=20)


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
    context = build_execution_context(
        root,
        requested_profile=requested,
        flow_authorized=True,
    )
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
    print(f"Rama: {proposal.branch}")
    print("Archivos que se incluirán:")
    for change in proposal.changes:
        print(f"- {change.status} {change.path}")
    print(f"Mensaje propuesto: {proposal.message}")
    if not args.yes:
        print("Commit no ejecutado. Repite con --yes después de revisar archivos y mensaje.")
        return 0

    if manual.required:
        if not args.confirm_manual_verification:
            raise RuntimeError("Manual verification confirmation is required before commit")
        record_manual_verification(execution.workspace.root, manual)

    result = lifecycle.commit(proposal, confirmed=True, message=args.message)
    history = LocalExecutionHistoryStore(root)
    snapshot = history.snapshot(execution.workspace.root)
    updated = build_live_runner(root).resume(flow_id=execution.flow.flow_id, project_root=root)
    archive_terminal(root, updated, snapshot)
    print(f"Commit creado: {result.sha}")
    print(f"Mensaje: {result.message}")
    if manual.required:
        print("Verificación manual: confirmada y archivada.")
    print("Flujo cerrado. Push y PR siguen siendo manuales.")
    return 0


def run_history(args, root: Path) -> int:
    store = LocalExecutionHistoryStore(root)
    all_records = store.list(kind=args.kind, state=args.state)
    visible = all_records[: max(0, args.limit)]
    completed = sum(item.state == "completed" for item in all_records)
    cancelled = sum(item.state == "cancelled" for item in all_records)
    durations = [item.duration_seconds for item in all_records if item.duration_seconds is not None]
    average = sum(durations) / len(durations) if durations else None
    print(f"Ejecuciones: {len(all_records)} | completadas: {completed} | canceladas: {cancelled}")
    if average is not None:
        print(f"Duración media: {average:.1f}s")
    for record in visible:
        duration = f"{record.duration_seconds:.1f}s" if record.duration_seconds is not None else "-"
        profile = record.permission_profile or "-"
        escalated = " escalated" if record.permission_escalated else ""
        print(
            f"- {record.flow_id} | {record.kind} | {record.state} | "
            f"{record.branch or '-'} | {duration} | profile={profile}{escalated} | {record.label or '-'}"
        )
    if not visible:
        print("Sin ejecuciones registradas")
    return 0
