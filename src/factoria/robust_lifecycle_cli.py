from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from factoria.application.agent_flow_runtime import build_live_runner
from factoria.application.artifacts import FlowArtifactStore
from factoria.application.branch_lifecycle import BranchLifecycleError, GitBranchLifecycle
from factoria.application.flow_service import FlowService
from factoria.application.governance import ExecutionGovernor, GovernedAction
from factoria.application.history import LocalExecutionHistoryStore
from factoria.application.policy_runtime import build_execution_context
from factoria.application.state_store import LocalFlowStateStore
from factoria.cli_lifecycle import archive_terminal
from factoria.domain.permissions import PermissionProfile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="factoria")
    parser.add_argument("--project", default=".")
    parser.add_argument("--read-only", action="store_true")
    parser.add_argument(
        "--profile",
        choices=tuple(profile.value for profile in PermissionProfile),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    resume = sub.add_parser("resume", help="Resume an interrupted flow safely")
    resume.add_argument("flow_id", nargs="?")
    resume.add_argument("--approve-plan", action="store_true")
    resume.add_argument("--approve-final", action="store_true")
    resume.add_argument(
        "--switch-branch",
        action="store_true",
        help="Explicitly switch to the flow branch when the worktree is clean",
    )

    cancel = sub.add_parser("cancel", help="Cancel a flow and optionally delete its branch")
    cancel.add_argument("flow_id", nargs="?")
    cancel.add_argument("--reason")
    cancel.add_argument("--yes", action="store_true", help="Confirm flow cancellation/workspace cleanup")
    cancel.add_argument("--delete-branch", action="store_true", help="Request branch deletion after cancellation")
    cancel.add_argument(
        "--confirm-delete-branch",
        action="store_true",
        help="Separate confirmation for deleting the associated Git branch",
    )
    cancel.add_argument(
        "--backup-branch",
        help="Create this backup branch before deleting a branch with unique commits",
    )
    return parser


def _root(args: argparse.Namespace) -> Path:
    root = Path(args.project).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Project root does not exist: {root}")
    return root


def _services(root: Path):
    artifacts = FlowArtifactStore(root)
    store = LocalFlowStateStore(artifacts)
    service = FlowService(artifacts=artifacts, state_store=store)
    return service, store, artifacts


def _requested_profile(args: argparse.Namespace) -> PermissionProfile | None:
    return PermissionProfile(args.profile) if args.profile else None


def _session(execution) -> dict[str, object] | None:
    path = execution.workspace.root / "agent-flow.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _list_incomplete(store: LocalFlowStateStore) -> int:
    executions = tuple(store.incomplete())
    if not executions:
        print("No hay flujos interrumpidos.")
        return 0
    print("Flujos interrumpidos:")
    for execution in executions:
        session = _session(execution) or {}
        branch = session.get("branch") or "-"
        phase = session.get("phase") or "-"
        label = execution.label or "-"
        print(
            f"- {execution.flow.flow_id} | {execution.flow.kind} | "
            f"{execution.flow.state.value} | branch={branch} | phase={phase} | {label}"
        )
    print("Elige un flow_id explícito para continuar.")
    return 2


def _workspace_files(execution) -> tuple[str, ...]:
    root = execution.workspace.root
    if not root.exists():
        return ()
    return tuple(
        str(path.relative_to(root))
        for path in sorted(root.rglob("*"))
        if path.is_file()
    )


def _cmd_resume(args: argparse.Namespace, root: Path) -> int:
    if args.read_only:
        raise PermissionError("--read-only forbids changing flow state")
    service, store, _ = _services(root)
    if args.flow_id is None:
        return _list_incomplete(store)

    execution = store.load(args.flow_id)
    session = _session(execution)
    if session is None:
        context = build_execution_context(
            root,
            requested_profile=_requested_profile(args),
            flow_authorized=True,
        )
        ExecutionGovernor().assert_allowed(GovernedAction.WRITE, context)
        updated = service.resume(execution)
        print(f"Reanudado: {updated.flow.flow_id} -> {updated.flow.state.value}")
        return 0

    flow_branch = str(session.get("branch") or "")
    phase = str(session.get("phase") or "unknown")
    branches = GitBranchLifecycle(root)
    if not flow_branch or not branches.branch_exists(flow_branch):
        raise BranchLifecycleError(
            f"La rama asociada al flujo no existe: {flow_branch or '<sin rama>'}"
        )

    current = subprocess.run(
        ["git", "-C", str(root), "branch", "--show-current"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    if current != flow_branch:
        if not args.switch_branch:
            raise BranchLifecycleError(
                f"El flujo pertenece a {flow_branch!r}; rama actual {current!r}. "
                "Usa --switch-branch para cambiar explícitamente si el árbol está limpio."
            )
        branches.switch_to_flow_branch(flow_branch)
        print(f"Rama cambiada explícitamente a: {flow_branch}")

    inspection = branches.inspect(flow_branch)
    if inspection.has_worktree_changes:
        print("Aviso: el árbol de trabajo contiene cambios pendientes:")
        for line in inspection.worktree_changes:
            print(f"- {line}")
        if phase == "awaiting_plan_approval":
            raise BranchLifecycleError(
                "El repositorio cambió mientras el plan esperaba aprobación. "
                "No se ejecutará un plan potencialmente obsoleto; revisa los cambios o cancela y regenera el flujo."
            )

    context = build_execution_context(
        root,
        requested_profile=_requested_profile(args),
        flow_authorized=True,
    )
    governor = ExecutionGovernor()
    governor.assert_allowed(GovernedAction.WRITE, context)
    governor.assert_allowed(GovernedAction.COMMAND, context)

    history = LocalExecutionHistoryStore(root)
    snapshot = history.snapshot(execution.workspace.root)
    updated = build_live_runner(root).resume(
        flow_id=execution.flow.flow_id,
        project_root=root,
        approve_plan=args.approve_plan,
        approve_final=args.approve_final,
    )
    archive_terminal(root, updated, snapshot)
    print(f"Reanudado: {updated.flow.flow_id} -> {updated.flow.state.value}")
    return 0


def _cmd_cancel(args: argparse.Namespace, root: Path) -> int:
    if args.read_only:
        raise PermissionError("--read-only forbids cancellation")
    service, store, _ = _services(root)
    if args.flow_id is None:
        return _list_incomplete(store)

    execution = store.load(args.flow_id)
    session = _session(execution) or {}
    flow_branch = str(session.get("branch") or "")
    files = _workspace_files(execution)

    print(f"Flujo: {execution.flow.flow_id}")
    print(f"Estado: {execution.flow.state.value}")
    print(f"Rama asociada: {flow_branch or 'desconocida'}")
    print(f"Workspace temporal: {execution.workspace.root}")
    if files:
        print("Artefactos temporales que se eliminarán al cancelar:")
        for item in files:
            print(f"- {item}")
    else:
        print("Artefactos temporales: ninguno")

    branches = GitBranchLifecycle(root)
    inspection = None
    if flow_branch and branches.branch_exists(flow_branch):
        inspection = branches.inspect(flow_branch)
        if inspection.worktree_changes:
            print("Cambios de trabajo NO eliminados por la cancelación:")
            for line in inspection.worktree_changes:
                print(f"- {line}")
        if inspection.unique_commits:
            print("ADVERTENCIA: la rama contiene commits únicos respecto a main:")
            for commit in inspection.unique_commits:
                print(f"- {commit.sha[:12]} {commit.subject}")
            print("Factoria recomienda integrar o respaldar esos commits antes de borrar la rama.")

    context = build_execution_context(
        root,
        requested_profile=_requested_profile(args),
        flow_authorized=True,
        destructive_confirmed=args.yes,
    )
    decision = ExecutionGovernor().evaluate(GovernedAction.DESTRUCTIVE, context)
    if not decision.allowed:
        raise PermissionError(decision.reason or "Cancellation blocked by permission policy")
    if not args.yes:
        print("Cancelación no ejecutada. Repite con --yes después de revisar exactamente lo que se eliminará.")
        return 2

    history = LocalExecutionHistoryStore(root)
    snapshot = history.snapshot(execution.workspace.root)
    updated = service.cancel(execution, reason=args.reason)
    archive_terminal(root, updated, snapshot)
    print("Flujo cancelado; los cambios del repositorio no se han descartado.")

    if not args.delete_branch:
        print("Rama conservada. Su eliminación es una acción separada.")
        return 0
    if not flow_branch:
        raise BranchLifecycleError("No hay rama asociada que pueda eliminarse de forma segura")
    if flow_branch == branches.base_branch:
        raise BranchLifecycleError("Factoria nunca elimina la rama base main al cancelar un flujo")
    if not args.confirm_delete_branch:
        print(
            "Rama NO eliminada. Para borrarla añade --delete-branch --confirm-delete-branch "
            "en una cancelación confirmada."
        )
        return 2

    # Re-inspect after workspace cleanup because .factoria/work may have changed.
    inspection = branches.inspect(flow_branch)
    if inspection.unique_commits and not args.backup_branch:
        print("Rama NO eliminada: contiene commits únicos.")
        print("Indica --backup-branch <nombre> para crear una copia explícita antes del borrado.")
        return 2

    backup = branches.delete_branch(flow_branch, backup_name=args.backup_branch)
    if backup:
        print(f"Backup creado: {backup}")
    print(f"Rama eliminada: {flow_branch}")
    return 0


def run_robust_lifecycle_cli(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        root = _root(args)
        if args.command == "resume":
            return _cmd_resume(args, root)
        if args.command == "cancel":
            return _cmd_cancel(args, root)
        parser.error(f"Unknown command: {args.command}")
    except (
        BranchLifecycleError,
        FileNotFoundError,
        PermissionError,
        RuntimeError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0
