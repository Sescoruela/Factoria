from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path

from factoria.application.agent_flow_runtime import LiveAgentFlowError, build_live_runner
from factoria.application.artifacts import FlowArtifactStore
from factoria.application.flow_service import FlowService
from factoria.application.governance import ExecutionGovernor, GovernedAction
from factoria.application.history import LocalExecutionHistoryStore
from factoria.application.memory_flows import MemoryInitFlow, MemoryUpdateFlow
from factoria.application.policy_runtime import build_execution_context
from factoria.application.state_store import LocalFlowStateStore
from factoria.cli_lifecycle import archive_terminal, register_lifecycle_commands, run_commit, run_history
from factoria.config.loader import ConfigError, load_project_config
from factoria.domain.permissions import PermissionProfile
from factoria.memory.detectors import BasicTechnologyDetector, DirectoryModuleDetector, GitActivityAnalyzer
from factoria.memory.git_staleness import GitMemoryStalenessInspector
from factoria.memory.initializer import MemoryInitializer
from factoria.memory.loader import MemoryFormatError, load_project_memory
from factoria.memory.updater import RepositoryMemoryAnalyzer, describe_memory_changes
from factoria.plugins.registry import PluginRegistry, PluginSource

FACTORIA_VERSION = "0.1.0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="factoria", description="Factoria development-flow CLI")
    parser.add_argument("--project", default=".", help="Project root (default: current directory)")
    parser.add_argument("--read-only", action="store_true", help="Forbid writes and project command execution")
    parser.add_argument(
        "--profile",
        choices=tuple(profile.value for profile in PermissionProfile),
        help="Temporary execution permission profile for this command",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    memory_init = sub.add_parser("memoria-init", help="Propose and initialize project memory")
    memory_init.add_argument("--name")
    memory_init.add_argument("--purpose", default="")
    memory_init.add_argument("--yes", action="store_true", help="Confirm writing the proposed memory")

    memory_update = sub.add_parser("memoria-update", help="Review and update persisted project memory")
    memory_update.add_argument("--yes", action="store_true", help="Confirm writing the reviewed memory")

    fix = sub.add_parser("fix", help="Start and execute a fix flow with coding agents")
    fix.add_argument("title")
    fix.add_argument("--label")
    fix.add_argument("--branch", help="Branch to create when starting from main")
    fix.add_argument("--tool", choices=("codex", "opencode"), help="Preferred agent tool")
    fix.add_argument("--large", action="store_true", help="Treat the fix as feature-like and require plan/final approval")
    fix.add_argument("--update-memory", action="store_true", help="Request a documentation/memory proposal")

    feature = sub.add_parser("feature", help="Start and execute a governed feature flow with coding agents")
    feature.add_argument("title")
    feature.add_argument("--label")
    feature.add_argument("--branch", help="Branch to create when starting from main")
    feature.add_argument("--tool", choices=("codex", "opencode"), help="Preferred agent tool")

    status = sub.add_parser("status", help="Show project Factoria status")
    status.add_argument("--all", action="store_true", help="Include terminal flows when available")

    resume = sub.add_parser("resume", help="Resume an interrupted flow")
    resume.add_argument("flow_id", nargs="?")
    resume.add_argument("--approve-plan", action="store_true", help="Approve a persisted plan and continue implementation")
    resume.add_argument("--approve-final", action="store_true", help="Approve the reviewed final result")

    pause = sub.add_parser("pause", help="Pause an active flow")
    pause.add_argument("flow_id")
    pause.add_argument("--reason")

    cancel = sub.add_parser("cancel", help="Cancel an active flow")
    cancel.add_argument("flow_id")
    cancel.add_argument("--reason")
    cancel.add_argument("--yes", action="store_true", help="Confirm workspace deletion")

    register_lifecycle_commands(sub)

    plugins = sub.add_parser("plugins", help="List discovered plugins")
    plugins.add_argument("--personal", action="append", default=[])
    plugins.add_argument("--organization", action="append", default=[])
    plugins.add_argument("--builtin", action="append", default=[])

    return parser


def _root(args: argparse.Namespace) -> Path:
    root = Path(args.project).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Project root does not exist: {root}")
    return root


def _services(root: Path) -> tuple[FlowService, LocalFlowStateStore, FlowArtifactStore]:
    artifacts = FlowArtifactStore(root)
    store = LocalFlowStateStore(artifacts)
    return FlowService(artifacts=artifacts, state_store=store), store, artifacts


def _git_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _choose_execution(store: LocalFlowStateStore, flow_id: str | None):
    incomplete = tuple(store.incomplete())
    if flow_id is not None:
        return store.load(flow_id)
    if len(incomplete) == 1:
        return incomplete[0]
    if not incomplete:
        raise RuntimeError("No interrupted flows found")
    ids = ", ".join(item.flow.flow_id for item in incomplete)
    raise RuntimeError(f"Multiple interrupted flows found; choose one: {ids}")


def _memory_thresholds(root: Path):
    config = load_project_config(root / ".factoria" / "config.toml")
    return config.memory.stale_after_commits


def _requested_profile(args: argparse.Namespace) -> PermissionProfile | None:
    return PermissionProfile(args.profile) if args.profile else None


def _govern(
    args: argparse.Namespace,
    root: Path,
    action: GovernedAction,
    *,
    flow_authorized: bool = False,
    destructive_confirmed: bool = False,
):
    context = build_execution_context(
        root,
        requested_profile=_requested_profile(args),
        flow_authorized=flow_authorized,
        destructive_confirmed=destructive_confirmed,
    )
    return ExecutionGovernor().assert_allowed(action, context)


def _cmd_memory_init(args: argparse.Namespace, root: Path) -> int:
    if args.read_only and args.yes:
        raise PermissionError("--read-only forbids writing project memory")
    initializer = MemoryInitializer(
        technology_detector=BasicTechnologyDetector(),
        module_detector=DirectoryModuleDetector(),
        activity_analyzer=GitActivityAnalyzer(),
        factoria_version=FACTORIA_VERSION,
    )
    flow = MemoryInitFlow(initializer)
    proposal = flow.propose(
        root,
        project_name=args.name or root.name,
        reviewed_commit=_git_head(root),
        purpose=args.purpose,
    )
    memory = proposal.memory
    print(f"Proyecto: {memory.project_name}")
    print(f"Tipo propuesto: {memory.metadata.project_kind.value if memory.metadata else 'unknown'}")
    print("Tecnologías: " + (", ".join(memory.technologies) or "ninguna detectada"))
    print("Módulos: " + (", ".join(item.name for item in memory.modules) or "ninguno detectado"))
    print(
        f"Actividad 30d: {proposal.activity.commits_last_30_days} commits, "
        f"{proposal.activity.active_branches} ramas"
    )
    if not args.yes:
        print("Propuesta no escrita. Repite con --yes tras revisarla.")
        return 0
    _govern(args, root, GovernedAction.WRITE)
    written = flow.apply(root, proposal.confirm())
    for item in written:
        print(f"Escrito: {item.path.relative_to(root)}")
    return 0


def _cmd_memory_update(args: argparse.Namespace, root: Path) -> int:
    current = load_project_memory(root)
    thresholds = _memory_thresholds(root)
    staleness = GitMemoryStalenessInspector().inspect(
        root,
        current,
        threshold_overrides=thresholds,
    )
    analyzer = RepositoryMemoryAnalyzer(
        technology_detector=BasicTechnologyDetector(),
        module_detector=DirectoryModuleDetector(),
    )
    preview = analyzer.analyze(root, current)
    changes = describe_memory_changes(current, preview, staleness)
    flow = MemoryUpdateFlow(analyzer=analyzer, factoria_version=FACTORIA_VERSION)
    proposal = flow.propose(
        root,
        current,
        reviewed_commit=_git_head(root),
        changes=changes,
    )

    print(f"Proyecto: {current.project_name}")
    print(f"Commits desde revisión: {staleness.commits_since_review}")
    if staleness.stale_documents:
        print("Memoria potencialmente desactualizada: " + ", ".join(item.value for item in staleness.stale_documents))
    else:
        print("Memoria: dentro de los umbrales de revisión")
    print("Propuesta:")
    for change in proposal.changes:
        evidence = f" [{'; '.join(change.evidence)}]" if change.evidence else ""
        print(f"- {change.target}: {change.reason}{evidence}")

    if args.read_only:
        print("--read-only: propuesta analizada; no se escribirá ningún archivo.")
        return 0
    if not args.yes:
        print("Propuesta no escrita. Repite con --yes tras revisarla.")
        return 0

    _govern(args, root, GovernedAction.WRITE)
    written = flow.apply(root, proposal.confirm())
    for path in written:
        print(f"Actualizado: {path.relative_to(root)}")
    return 0


def _cmd_start_flow(args: argparse.Namespace, root: Path, kind: str) -> int:
    if args.read_only:
        raise PermissionError("--read-only forbids creating or executing agent flows")
    context = build_execution_context(root, requested_profile=_requested_profile(args))
    governor = ExecutionGovernor()
    governor.assert_allowed(GovernedAction.WRITE, context)
    governor.assert_allowed(GovernedAction.COMMAND, context)
    flow_id = str(uuid.uuid4())
    runner = build_live_runner(root)
    execution = runner.start(
        kind=kind,
        title=args.title,
        project_root=root,
        flow_id=flow_id,
        branch=args.branch,
        preferred_tool=args.tool,
        label=args.label,
        large_fix=bool(getattr(args, "large", False)),
        update_memory=bool(getattr(args, "update_memory", False)),
        base_permission_profile=context.base_profile,
        requested_permission_profile=context.requested_profile,
    )
    effective = context.effective_profile
    print(f"{kind} iniciado: {execution.flow.flow_id}")
    print(f"Perfil de permisos: {effective.value}")
    if context.escalated:
        print(f"Perfil base: {context.base_profile.value} (escalado temporal registrado)")
    print(f"Estado: {execution.flow.state.value}")
    workspace = root / ".factoria" / "work" / flow_id
    session_path = workspace / "agent-flow.json"
    if session_path.exists():
        phase = json.loads(session_path.read_text(encoding="utf-8"))["phase"]
        print(f"Fase: {phase}")
    if execution.flow.state.value == "paused":
        print("Revisa los artefactos del flujo antes de continuar con `factoria resume`.")
    return 0


def _cmd_status(root: Path) -> int:
    _, store, _ = _services(root)
    incomplete = tuple(store.incomplete())
    agents = root / "AGENTS.md"
    print(f"Proyecto: {root.name}")
    if not agents.exists():
        print("Memoria: no inicializada")
    else:
        memory = load_project_memory(root)
        staleness = GitMemoryStalenessInspector().inspect(
            root,
            memory,
            threshold_overrides=_memory_thresholds(root),
        )
        if staleness.stale_documents:
            docs = ", ".join(item.value for item in staleness.stale_documents)
            print(f"Memoria: potencialmente desactualizada ({docs})")
        else:
            print(f"Memoria: al día ({staleness.commits_since_review} commits desde revisión)")
    if not incomplete:
        print("Flujos activos: ninguno")
        return 0
    print("Flujos activos:")
    for item in incomplete:
        label = f" ({item.label})" if item.label else ""
        session_path = item.workspace.root / "agent-flow.json"
        phase = ""
        if session_path.exists():
            session = json.loads(session_path.read_text(encoding="utf-8"))
            phase_name = session.get("phase")
            profile = session.get("permission_profile")
            phase = f" / {phase_name}" if phase_name else ""
            if profile:
                phase += f" / profile={profile}"
        print(f"- {item.flow.flow_id}: {item.flow.kind} / {item.flow.state.value}{phase}{label}")
    return 0


def _cmd_resume(args: argparse.Namespace, root: Path) -> int:
    if args.read_only:
        raise PermissionError("--read-only forbids changing flow state")
    _govern(args, root, GovernedAction.WRITE, flow_authorized=True)
    service, store, _ = _services(root)
    execution = _choose_execution(store, args.flow_id)
    history = LocalExecutionHistoryStore(root)
    snapshot = history.snapshot(execution.workspace.root)
    session_path = execution.workspace.root / "agent-flow.json"
    if session_path.exists():
        _govern(args, root, GovernedAction.COMMAND, flow_authorized=True)
        runner = build_live_runner(root)
        updated = runner.resume(
            flow_id=execution.flow.flow_id,
            project_root=root,
            approve_plan=args.approve_plan,
            approve_final=args.approve_final,
        )
    else:
        updated = service.resume(execution)
    archive_terminal(root, updated, snapshot)
    print(f"Reanudado: {updated.flow.flow_id} -> {updated.flow.state.value}")
    return 0


def _cmd_pause(args: argparse.Namespace, root: Path) -> int:
    if args.read_only:
        raise PermissionError("--read-only forbids changing flow state")
    _govern(args, root, GovernedAction.WRITE, flow_authorized=True)
    service, store, _ = _services(root)
    execution = store.load(args.flow_id)
    updated = service.pause(execution, reason=args.reason)
    print(f"Pausado: {updated.flow.flow_id}")
    return 0


def _cmd_cancel(args: argparse.Namespace, root: Path) -> int:
    if args.read_only:
        raise PermissionError("--read-only forbids cancellation")
    context = build_execution_context(
        root,
        requested_profile=_requested_profile(args),
        flow_authorized=True,
        destructive_confirmed=args.yes,
    )
    decision = ExecutionGovernor().evaluate(GovernedAction.DESTRUCTIVE, context)
    if not decision.allowed:
        raise PermissionError(decision.reason or "Cancellation blocked by permission policy")
    # Cancellation keeps its stronger product-level confirmation even in power profile.
    if not args.yes:
        print("Cancelación no ejecutada. Usa --yes para confirmar la eliminación del workspace temporal.")
        return 2
    service, store, _ = _services(root)
    execution = store.load(args.flow_id)
    history = LocalExecutionHistoryStore(root)
    snapshot = history.snapshot(execution.workspace.root)
    updated = service.cancel(execution, reason=args.reason)
    archive_terminal(root, updated, snapshot)
    print(f"Cancelado: {args.flow_id}")
    print("Nota: esta versión no elimina ramas Git asociadas.")
    return 0


def _cmd_plugins(args: argparse.Namespace) -> int:
    registry = PluginRegistry(factoria_version=FACTORIA_VERSION)
    roots: list[tuple[PluginSource, Path]] = []
    roots.extend((PluginSource.PERSONAL, Path(path).expanduser()) for path in args.personal)
    roots.extend((PluginSource.ORGANIZATION, Path(path).expanduser()) for path in args.organization)
    roots.extend((PluginSource.BUILTIN, Path(path).expanduser()) for path in args.builtin)
    registry.discover(roots)
    for record in registry.plugins:
        print(
            f"{record.manifest.name}\t{record.manifest.version}\t"
            f"{record.state.value}\t{record.source.name.lower()}\t{record.path}"
        )
    for record in registry.problems:
        details = "; ".join(record.warnings)
        print(f"ERROR\t{record.path}\t{details}")
    if not registry.plugins and not registry.problems:
        print("No plugins discovered")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        root = _root(args)
        if args.command == "memoria-init":
            return _cmd_memory_init(args, root)
        if args.command == "memoria-update":
            return _cmd_memory_update(args, root)
        if args.command in {"fix", "feature"}:
            return _cmd_start_flow(args, root, args.command)
        if args.command == "status":
            return _cmd_status(root)
        if args.command == "resume":
            return _cmd_resume(args, root)
        if args.command == "pause":
            return _cmd_pause(args, root)
        if args.command == "cancel":
            return _cmd_cancel(args, root)
        if args.command == "commit":
            _, store, _ = _services(root)
            return run_commit(args, root, _choose_execution(store, args.flow_id))
        if args.command == "history":
            return run_history(args, root)
        if args.command == "plugins":
            return _cmd_plugins(args)
        parser.error(f"Unknown command: {args.command}")
    except (
        ConfigError,
        FileNotFoundError,
        LiveAgentFlowError,
        MemoryFormatError,
        PermissionError,
        RuntimeError,
        ValueError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
