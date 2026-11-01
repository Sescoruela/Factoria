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


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv == ["--version"]:
        print(f"factoria {installed_version()}")
        return 0
    if not argv or argv[0] not in {"update", "rollback"}:
        from factoria.cli import main as cli_main

        return cli_main(argv)

    parser = build_update_parser()
    args = parser.parse_args(argv)
    service = UpdateService()
    state_path = Path.home() / ".factoria" / "update-state" / "previous.json"
    config_path = Path.home() / ".factoria" / "config.toml"

    try:
        if args.command == "update":
            source = service.discover_source_root(args.source)
            plan = service.inspect(
                source,
                remote=args.remote,
                branch=args.branch,
                current_version=installed_version(),
            )
            print(f"Versión actual: {plan.current_version}")
            print(f"Versión objetivo: {plan.target_version}")
            print(f"Commit objetivo: {plan.target_sha[:12]}")
            if not plan.available:
                print("Factoria ya está en la versión más reciente disponible.")
                return 0

            print("Cambios detectados:")
            if plan.changes:
                for change in plan.changes:
                    print(f"- {change}")
            else:
                print("- No hay resumen de commits disponible.")
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
            if not args.yes:
                print("Actualización no aplicada. Repite con --yes después de revisar los cambios.")
                return 0

            result = service.apply(
                plan,
                state_path=state_path,
                config_path=config_path,
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
