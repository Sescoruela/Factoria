from __future__ import annotations

import argparse
import subprocess
import sys
import uuid
from pathlib import Path

from factoria.application.artifacts import FlowArtifactStore
from factoria.application.flow_service import FlowService
from factoria.application.state_store import LocalFlowStateStore
from factoria.memory.detectors import BasicTechnologyDetector, DirectoryModuleDetector, GitActivityAnalyzer
from factoria.memory.initializer import MemoryInitializer
from factoria.application.memory_flows import MemoryInitFlow
from factoria.plugins.registry import PluginRegistry, PluginSource

FACTORIA_VERSION = "0.1.0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="factoria", description="Factoria development-flow CLI")
    parser.add_argument("--project", default=".", help="Project root (default: current directory)")
    parser.add_argument("--read-only", action="store_true", help="Forbid writes and project command execution")
    sub = parser.add_subparsers(dest="command", required=True)

    memory_init = sub.add_parser("memoria-init", help="Propose and initialize project memory")
    memory_init.add_argument("--name")
    memory_init.add_argument("--purpose", default="")
    memory_init.add_argument("--yes", action="store_true", help="Confirm writing the proposed memory")

    memory_update = sub.add_parser("memoria-update", help="Review project memory")
    memory_update.add_argument("--yes", action="store_true")

    for kind in ("fix", "feature"):
        flow = sub.add_parser(kind, help=f"Start a {kind} flow")
        flow.add_argument("title")
        flow.add_argument("--label")

    status = sub.add_parser("status", help="Show project Factoria status")
    status.add_argument("--all", action="store_true", help="Include terminal flows when available")

    resume = sub.add_parser("resume", help="Resume an interrupted flow")
    resume.add_argument("flow_id", nargs="?")

    pause = sub.add_parser("pause", help="Pause an active flow")
    pause.add_argument("flow_id")
    pause.add_argument("--reason")

    cancel = sub.add_parser("cancel", help="Cancel an active flow")
    cancel.add_argument("flow_id")
    cancel.add_argument("--reason")
    cancel.add_argument("--yes", action="store_true", help="Confirm workspace deletion")

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
    written = flow.apply(root, proposal.confirm())
    for item in written:
        print(f"Escrito: {item.path.relative_to(root)}")
    return 0


def _cmd_memory_update(args: argparse.Namespace, root: Path) -> int:
    agents = root / "AGENTS.md"
    if not agents.exists():
        raise FileNotFoundError("No project memory found; run `factoria memoria-init` first")
    if args.read_only:
        print("Memoria encontrada. --read-only: no se realizarán cambios.")
        return 0
    print(
        "La revisión automática de memoria todavía necesita el cargador estructurado de memoria; "
        "no se ha modificado ningún archivo."
    )
    return 0


def _cmd_start_flow(args: argparse.Namespace, root: Path, kind: str) -> int:
    if args.read_only:
        raise PermissionError("--read-only forbids creating flow workspaces")
    service, _, artifacts = _services(root)
    flow_id = str(uuid.uuid4())
    execution = service.create(flow_id=flow_id, kind=kind, label=args.label or args.title)
    task = f"# {kind.title()}\n\n{args.title}\n"
    artifacts.write_text(flow_id, "task.md", task)
    execution = service.start(execution)
    print(f"{kind} iniciado: {execution.flow.flow_id}")
    print(f"Estado: {execution.flow.state.value}")
    return 0


def _cmd_status(root: Path) -> int:
    _, store, _ = _services(root)
    incomplete = tuple(store.incomplete())
    memory = root / "AGENTS.md"
    print(f"Proyecto: {root.name}")
    print(f"Memoria: {'presente' if memory.exists() else 'no inicializada'}")
    if not incomplete:
        print("Flujos activos: ninguno")
        return 0
    print("Flujos activos:")
    for item in incomplete:
        label = f" ({item.label})" if item.label else ""
        print(f"- {item.flow.flow_id}: {item.flow.kind} / {item.flow.state.value}{label}")
    return 0


def _cmd_resume(args: argparse.Namespace, root: Path) -> int:
    if args.read_only:
        raise PermissionError("--read-only forbids changing flow state")
    service, store, _ = _services(root)
    execution = _choose_execution(store, args.flow_id)
    updated = service.resume(execution)
    print(f"Reanudado: {updated.flow.flow_id} -> {updated.flow.state.value}")
    return 0


def _cmd_pause(args: argparse.Namespace, root: Path) -> int:
    if args.read_only:
        raise PermissionError("--read-only forbids changing flow state")
    service, store, _ = _services(root)
    execution = store.load(args.flow_id)
    updated = service.pause(execution, reason=args.reason)
    print(f"Pausado: {updated.flow.flow_id}")
    return 0


def _cmd_cancel(args: argparse.Namespace, root: Path) -> int:
    if args.read_only:
        raise PermissionError("--read-only forbids cancellation")
    if not args.yes:
        print("Cancelación no ejecutada. Usa --yes para confirmar la eliminación del workspace temporal.")
        return 2
    service, store, _ = _services(root)
    execution = store.load(args.flow_id)
    service.cancel(execution, reason=args.reason)
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
        if args.command == "plugins":
            return _cmd_plugins(args)
        parser.error(f"Unknown command: {args.command}")
    except (FileNotFoundError, PermissionError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
