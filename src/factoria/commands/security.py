from __future__ import annotations

import argparse
from pathlib import Path

from factoria.security import SecretIncidentStore, SecretScanner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="factoria security")
    parser.add_argument("--project", default=".")
    sub = parser.add_subparsers(dest="security_command", required=True)
    sub.add_parser("incidents", help="List persisted secret incidents")
    resolve = sub.add_parser(
        "resolve", help="Confirm rotation/revocation and verify secret removal"
    )
    resolve.add_argument("incident_id")
    resolve.add_argument(
        "--confirm-rotation",
        action="store_true",
        help="Confirm the credential was rotated/revoked outside Factoria",
    )
    return parser


def run_security_cli(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.project).expanduser().resolve()
    store = SecretIncidentStore(root)
    if args.security_command == "incidents":
        records = store.list()
        if not records:
            print("Incidentes de seguridad: ninguno")
            return 0
        for item in records:
            print(
                f"- {item.incident_id} | {item.status.value} | {item.secret_type} | "
                f"{item.source}@{item.location} | fingerprint={item.fingerprint}"
            )
        return 0

    if not args.confirm_rotation:
        print(
            "Resolución no ejecutada. Rota/revoca la credencial fuera de Factoria y repite con --confirm-rotation."
        )
        return 2
    resolved = store.confirm_rotation_and_resolve(args.incident_id, SecretScanner())
    print(f"Incidente resuelto: {resolved.incident_id}")
    print("Factoria verificó que el fingerprint detectado ya no aparece en el ámbito verificable.")
    return 0
