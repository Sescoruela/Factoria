from __future__ import annotations

import argparse
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from factoria.application.governance import ExecutionGovernor, GovernedAction
from factoria.application.memory_bootstrap import MemoryBootstrapService
from factoria.application.policy_runtime import build_execution_context
from factoria.domain.models import ProjectKind
from factoria.domain.permissions import PermissionProfile
from factoria.memory.detectors import (
    BasicTechnologyDetector,
    DirectoryModuleDetector,
    GitActivityAnalyzer,
)
from factoria.memory.initializer import MemoryInitializer


def build_memory_init_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="factoria")
    parser.add_argument("--project", default=".", help="Project root (default: current directory)")
    parser.add_argument("--read-only", action="store_true", help="Preview only; forbid writes")
    parser.add_argument(
        "--profile",
        choices=tuple(profile.value for profile in PermissionProfile),
        help="Temporary execution permission profile",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    memory_init = sub.add_parser("memoria-init", help="Propose complete first-time project memory")
    memory_init.add_argument("--name")
    memory_init.add_argument("--purpose", default="")
    memory_init.add_argument(
        "--kind",
        choices=tuple(kind.value for kind in ProjectKind),
        help="Override the activity-based active/maintenance proposal",
    )
    memory_init.add_argument(
        "--yes", action="store_true", help="Confirm the complete proposal and write it"
    )
    return parser


def run_memory_init_cli(argv: list[str]) -> int:
    parser = build_memory_init_parser()
    args = parser.parse_args(argv)
    root = Path(args.project).expanduser().resolve()
    if not root.is_dir():
        print(f"error: Project root does not exist: {root}", file=sys.stderr)
        return 1
    if args.read_only and args.yes:
        print("error: --read-only forbids writing project memory", file=sys.stderr)
        return 1

    try:
        initializer = MemoryInitializer(
            technology_detector=BasicTechnologyDetector(),
            module_detector=DirectoryModuleDetector(),
            activity_analyzer=GitActivityAnalyzer(),
            factoria_version=_factoria_version(),
        )
        service = MemoryBootstrapService(initializer)
        proposal = service.propose(
            root,
            project_name=args.name or root.name,
            reviewed_commit=_git_head(root),
            purpose=args.purpose,
            project_kind=ProjectKind(args.kind) if args.kind else None,
        )
        _print_proposal(root, proposal)
        if args.read_only:
            print("--read-only: propuesta analizada; no se escribirá ningún archivo.")
            return 0
        if not args.yes:
            print("Propuesta no escrita. Repite con --yes tras revisar todos los datos propuestos.")
            return 0

        requested = PermissionProfile(args.profile) if args.profile else None
        context = build_execution_context(root, requested_profile=requested)
        ExecutionGovernor().assert_allowed(GovernedAction.WRITE, context)
        written = service.apply(root, proposal.confirm())
        for path in written:
            print(f"Escrito: {path.relative_to(root)}")
        return 0
    except (
        FileExistsError,
        PermissionError,
        RuntimeError,
        ValueError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _print_proposal(root: Path, proposal) -> None:
    memory = proposal.memory
    kind = memory.metadata.project_kind.value if memory.metadata else "unknown"
    suggested = proposal.activity.suggested_kind.value
    print(f"Proyecto: {memory.project_name}")
    print(f"Tipo propuesto: {kind} (heurística de actividad: {suggested})")
    print(
        f"Actividad 30d: {proposal.activity.commits_last_30_days} commits, "
        f"{proposal.activity.active_branches} ramas"
    )
    print("Tecnologías propuestas: " + (", ".join(memory.technologies) or "ninguna detectada"))
    print("Módulos propuestos:")
    if memory.modules:
        for module in memory.modules:
            print(f"- {module.name}: {', '.join(module.paths) or 'sin rutas'}")
    else:
        print("- ninguno")

    print("Dependencias propuestas:")
    if memory.dependencies:
        for source, targets in memory.dependencies.items():
            print(f"- {source} -> {', '.join(targets)}")
    else:
        print("- ninguna detectada con evidencia suficiente")

    print("Comandos de verificación propuestos:")
    if memory.confirmed_check_commands:
        for command in memory.confirmed_check_commands:
            scope = command.scope or "global"
            print(f"- {command.category}/{scope}: {' '.join(command.command)}")
    else:
        print("- ninguno detectado con evidencia suficiente")

    print("Prioridades no funcionales propuestas: " + ", ".join(memory.non_functional_priorities))
    print(
        "Reglas duras específicas del proyecto: "
        + (", ".join(memory.mandatory_rules) or "ninguna inferida")
    )
    print(f"Configuración propuesta: {proposal.config_target.relative_to(root)}")
    if proposal.write_config:
        for line in proposal.config_text.rstrip().splitlines():
            print(f"  {line}")
    else:
        print("  se preservará la configuración existente")

    if proposal.evidence:
        print("Evidencia de las propuestas:")
        for item in proposal.evidence:
            print(f"- {item.target}: {item.reason} [{item.source}]")
    for warning in proposal.warnings:
        print(f"Aviso: {warning}")
    print("Nada de lo anterior se considera confirmado hasta aplicar la propuesta con --yes.")


def _git_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _factoria_version() -> str:
    try:
        return version("factoria")
    except PackageNotFoundError:
        return "uninstalled"
