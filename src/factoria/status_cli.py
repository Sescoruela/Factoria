from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from factoria.application.status import OperationalStatusService
from factoria.config.loader import ConfigError


def build_status_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="factoria")
    parser.add_argument("--project", default=".", help="Project root (default: current directory)")
    parser.add_argument("--read-only", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--profile", help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True)
    status = sub.add_parser("status", help="Show operational Factoria status")
    status.add_argument("--all", action="store_true", help="Show up to 10 recent results instead of 5")
    return parser


def run_status_cli(argv: list[str]) -> int:
    parser = build_status_parser()
    args = parser.parse_args(argv)
    root = Path(args.project).expanduser().resolve()
    if not root.is_dir():
        print(f"error: Project root does not exist: {root}", file=sys.stderr)
        return 1
    try:
        report = OperationalStatusService().inspect(root, include_history=args.all)
    except (ConfigError, FileNotFoundError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print("FACTORIA STATUS")
    print(f"Proyecto: {report.project_name}")
    print(f"Rama: {report.branch} ({'cambios pendientes' if report.dirty else 'limpia'})")
    print(f"Tipo: {report.project_kind or 'sin confirmar'}")

    print("\nConfiguración efectiva")
    print(f"- Perfil: {report.effective_profile}")
    print(f"- Herramienta: {report.effective_tool or 'sin configurar'}")
    print(f"- Máx. agentes: {report.max_agents}")
    print("- Acciones bloqueadas (proyecto): " + (", ".join(report.blocked_actions) or "ninguna"))
    print(
        "- Acciones bloqueadas (organización): "
        + (", ".join(report.organization_blocked_actions) or "ninguna")
    )
    print("- Flujos permitidos: " + (", ".join(report.allowed_flows) or "todos salvo bloqueados"))
    print("- Flujos bloqueados: " + (", ".join(report.blocked_flows) or "ninguno"))

    print("\nMemoria")
    if not report.memory_initialized:
        print("- No inicializada")
    else:
        print(f"- Versión Factoria al revisar: {report.memory_version or 'desconocida'}")
        if report.memory_commits_since_review is not None:
            print(f"- Commits desde revisión: {report.memory_commits_since_review}")
        print(
            "- Documentos potencialmente stale: "
            + (", ".join(report.stale_documents) or "ninguno")
        )

    print("\nHerramientas")
    for tool in report.tools:
        capabilities = ", ".join(tool.capabilities) or "sin capacidades declaradas"
        print(f"- {tool.name}: {'disponible' if tool.available else 'no disponible'} | {capabilities}")

    print("\nFlujos activos")
    if not report.active_flows:
        print("- Ninguno")
    for flow in report.active_flows:
        details = [flow.kind, flow.state]
        if flow.phase:
            details.append(flow.phase)
        if flow.branch:
            details.append(f"branch={flow.branch}")
        if flow.blocked:
            details.append("BLOCKED")
        label = f" ({flow.label})" if flow.label else ""
        print(f"- {flow.flow_id}{label}: " + " / ".join(details))

    print("\nSeguridad")
    if not report.security.blocked:
        print("- Sin posibles secretos detectados en archivos modificados")
    else:
        print(f"- BLOQUEO: {report.security.finding_count} posible(s) secreto(s)")
        for item in report.security.summaries:
            print(f"  - {item}")

    print("\nResultados recientes")
    if not report.recent_results:
        print("- Sin ejecuciones archivadas")
    for item in report.recent_results:
        duration = f"{item.duration_seconds:.1f}s" if item.duration_seconds is not None else "?"
        branch = item.branch or "-"
        print(
            f"- {item.flow_id}: {item.kind} / {item.state} / branch={branch} / "
            f"duration={duration} / profile={item.permission_profile or '-'}"
        )

    print("\nAvisos")
    if not report.warnings:
        print("- Ninguno")
    else:
        for warning in report.warnings:
            print(f"- {warning}")

    print("\nSiguientes acciones")
    if not report.recommendations:
        print("- Ninguna acción prioritaria detectada")
    else:
        for recommendation in report.recommendations:
            print(f"- {recommendation}")
    return 0
