from __future__ import annotations

import argparse
import sys
from pathlib import Path

from factoria.application.self_update import UpdateError, UpdateService
from factoria.package_version import PackageVersionError, installed_semver
from factoria.versioning import SemVer


def installed_version() -> SemVer:
    try:
        return installed_semver()
    except PackageVersionError as exc:
        raise UpdateError(str(exc)) from exc


def build_update_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="factoria")
    sub = parser.add_subparsers(dest="command", required=True)

    update = sub.add_parser("update", help="Check for and apply a newer tagged Factoria release")
    update.add_argument("--source", type=Path, help="Factoria Git clone used to inspect releases")
    update.add_argument("--remote", default="origin", help="Git remote to inspect (default: origin)")
    update.add_argument(
        "--branch",
        default="main",
        help="Release channel branch; selected tags must be reachable from it (default: main)",
    )
    update.add_argument(
        "--tag",
        help="Specific SemVer release tag to inspect (for example v0.3.0); defaults to newest newer tag",
    )
    update.add_argument("--yes", action="store_true", help="Confirm installation of the reviewed tagged release")

    rollback = sub.add_parser("rollback", help="Restore the previous Factoria version")
    rollback.add_argument("--yes", action="store_true", help="Confirm rollback and managed-config restoration")
    return parser


def _primary_command(argv: list[str]) -> str | None:
    index = 0
    while index < len(argv):
        value = argv[index]
        if value in {"--project", "--profile"}:
            index += 2
            continue
        if value == "--read-only":
            index += 1
            continue
        if value.startswith("-"):
            return None
        return value
    return None


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv == ["--version"]:
        print(f"factoria {installed_version()}")
        return 0

    if not argv:
        from factoria.ui_agent_tools import run_agent_aware_ui_cli
        return run_agent_aware_ui_cli(["ui"])

    command = _primary_command(argv)
    if command in {"ui", "onboarding"}:
        from factoria.ui_agent_tools import run_agent_aware_ui_cli
        return run_agent_aware_ui_cli(argv)
    if command == "memoria-init":
        from factoria.memory_bootstrap_cli import run_memory_init_cli
        return run_memory_init_cli(argv)
    if command == "status":
        from factoria.status_cli import run_status_cli
        return run_status_cli(argv)
    if command == "plugins":
        from factoria.plugins_cli import run_plugins_cli
        return run_plugins_cli(argv)
    if command == "security":
        from factoria.security_cli import run_security_cli
        return run_security_cli(argv)
    if command in {"resume", "cancel"}:
        from factoria.robust_lifecycle_cli import run_robust_lifecycle_cli
        return run_robust_lifecycle_cli(argv)
    if argv[0] not in {"update", "rollback"}:
        from factoria.cli import main as cli_main
        return cli_main(argv)

    parser = build_update_parser()
    args = parser.parse_args(argv)
    service = UpdateService()
    base = Path.home() / ".factoria" / "update-state"
    state_path = base / "previous.json"
    provenance_path = base / "installed.json"
    config_path = Path.home() / ".factoria" / "config.toml"

    try:
        if args.command == "update":
            source = service.discover_source_root(args.source)
            plan = service.inspect(
                source,
                remote=args.remote,
                branch=args.branch,
                current_version=installed_version(),
                provenance_path=provenance_path,
                release_tag=args.tag,
            )
            print(f"Versión actual: {plan.current_version}")
            print(f"Release objetivo: {plan.release_tag}")
            print(f"Versión objetivo: {plan.target_version}")
            print(f"Commit objetivo: {plan.target_sha[:12]}")
            print(f"Tree objetivo: {plan.target_tree_sha[:12]}")
            print(f"Canal verificado: {plan.remote}/{plan.branch}")
            if plan.current_sha:
                print(f"Commit instalado: {plan.current_sha[:12]} (procedencia verificada)")
            else:
                print("Commit instalado: desconocido (rollback seguro no disponible)")
            if not plan.available:
                print("No hay una release más reciente disponible para este canal.")
                return 0
            if not args.yes:
                print("Actualización no aplicada. Repite con --yes después de revisar el plan.")
                return 0
            result = service.apply(
                plan,
                state_path=state_path,
                provenance_path=provenance_path,
                config_path=config_path,
                confirmed=True,
            )
            print(f"Actualización completada: {result.previous_version} -> {result.installed_version}")
            return 0

        plan = service.inspect_rollback(
            state_path=state_path,
            provenance_path=provenance_path,
            config_path=config_path,
        )
        print(f"Versión actual: {plan.current_version}")
        print(f"Versión a restaurar: {plan.previous_version}")
        print(f"Commit a restaurar: {plan.previous_sha[:12]}")
        if not args.yes:
            print("Rollback no aplicado. Repite con --yes después de revisar el plan.")
            return 0
        result = service.rollback(
            plan,
            state_path=state_path,
            provenance_path=provenance_path,
            config_path=config_path,
            confirmed=True,
        )
        print(f"Rollback completado: {result.previous_version} -> {result.installed_version}")
        return 0
    except (UpdateError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
