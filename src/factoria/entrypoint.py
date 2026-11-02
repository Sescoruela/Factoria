from __future__ import annotations

import argparse
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from factoria.application.self_update import UpdateError, UpdateService
from factoria.versioning import SemVer


def installed_version() -> SemVer:
    try:
        return SemVer.parse(version("factoria"))
    except PackageNotFoundError as exc:
        raise UpdateError("Factoria package metadata is unavailable") from exc


def build_update_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="factoria")
    sub = parser.add_subparsers(dest="command", required=True)

    update = sub.add_parser("update", help="Check for and apply a newer Factoria version")
    update.add_argument("--source", type=Path, help="Factoria Git clone used to inspect releases")
    update.add_argument("--remote", default="origin", help="Git remote to inspect (default: origin)")
    update.add_argument("--branch", default="main", help="Remote branch to inspect (default: main)")
    update.add_argument("--yes", action="store_true", help="Confirm installation of the proposed version")

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

    command = _primary_command(argv)
    if command == "memoria-init":
        from factoria.memory_bootstrap_cli import run_memory_init_cli
        return run_memory_init_cli(argv)
    if command == "status":
        from factoria.status_cli import run_status_cli
        return run_status_cli(argv)
    if command == "plugins":
        from factoria.plugins_cli import run_plugins_cli
        return run_plugins_cli(argv)
    if command in {"resume", "cancel"}:
        from factoria.robust_lifecycle_cli import run_robust_lifecycle_cli
        return run_robust_lifecycle_cli(argv)
    if not argv or argv[0] not in {"update", "rollback"}:
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
            )
            print(f"Versión actual: {plan.current_version}")
            print(f"Versión objetivo: {plan.target_version}")
            print(f"Commit objetivo: {plan.target_sha[:12]}")
            if plan.current_sha:
                print(f"Commit instalado: {plan.current_sha[:12]} (procedencia verificada)")
            else:
                print("Commit instalado: desconocido (rollback seguro no disponible)")
            if not plan.available:
                print("Factoria ya está en la versión más reciente disponible.")
                return 0

            print("Cambios detectados:")
            if plan.changes:
                for change in plan.changes:
                    print(f"- {change}")
            else:
                print("- No hay resumen fiable de commits disponible.")
            if plan.release and plan.release.notes:
                print("Notas de la versión:")
                for note in plan.release.notes:
                    print(f"- {note}")
            if plan.major_update:
                print("Aviso: actualización MAJOR; revisa compatibilidad antes de continuar.")
                if plan.release and plan.release.memory_changes:
                    print("Cambios de memoria:")
                    for note in plan.release.memory_changes:
                        print(f"- {note}")
                if plan.release and plan.release.config_changes:
                    print("Cambios de configuración:")
                    for note in plan.release.config_changes:
                        print(f"- {note}")
                print("Factoria no migra automáticamente la memoria del proyecto en esta versión.")
            if not plan.provenance_verified:
                print("Actualización bloqueada: no existe evidencia del commit exacto instalado para un rollback seguro.")
                return 1
            if not args.yes:
                print("Actualización no aplicada. Repite con --yes después de revisar los cambios.")
                return 0

            result = service.apply(
                plan,
                state_path=state_path,
                config_path=config_path,
                provenance_path=provenance_path,
                confirmed=True,
            )
            print(f"Factoria actualizada a {result.version} ({result.commit_sha[:12]}).")
            if result.health_ok:
                print("Health check: PASS")
                return 0
            print(f"Health check: FAIL ({result.health_details})")
            print("El rollback queda disponible con `factoria rollback --yes`.")
            return 1

        if not args.yes:
            print("Rollback no aplicado. Repite con --yes para confirmar.")
            return 0
        result = service.rollback(
            state_path=state_path,
            config_path=config_path,
            provenance_path=provenance_path,
            confirmed=True,
        )
        print(f"Factoria restaurada a {result.version} ({result.commit_sha[:12]}).")
        if result.health_ok:
            print("Health check: PASS")
            return 0
        print(f"Health check: FAIL ({result.health_details})")
        print("El estado de rollback se conserva para diagnóstico manual.")
        return 1
    except UpdateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
