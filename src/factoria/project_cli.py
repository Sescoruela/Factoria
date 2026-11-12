from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from factoria.application.native_workflow import NativeWorkflow
from factoria.application.project_integration import ProjectIntegration


def build_project_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="factoria")
    parser.add_argument("--project", default=".")
    parser.add_argument("--read-only", action="store_true")
    parser.add_argument("--profile", choices=("safe", "normal", "power"))
    group = parser.add_subparsers(dest="command", required=True)
    project = group.add_parser("project").add_subparsers(dest="action", required=True)
    prepare = project.add_parser(
        "prepare", help="Preview or generate shared configuration for Codex and OpenCode"
    )
    prepare.add_argument("--yes", action="store_true")
    project.add_parser("check", help="Check freshness and ownership without calling an LLM")
    project.add_parser("workflows", help="List configured workflow identifiers and base types")
    project.add_parser("relations", help="Read-only workflow, stage, agent and skill relationships")
    configuration = project.add_parser(
        "config", help="Inspect, migrate and recover saved configuration"
    ).add_subparsers(dest="config_action", required=True)
    configuration.add_parser("status")
    for action in ("migrate", "snapshot", "restore"):
        command = configuration.add_parser(action)
        if action == "restore":
            command.add_argument("backup_id")
        command.add_argument("--yes", action="store_true")
        command.add_argument("--token", help="Token returned by the reviewed preview")
    resources = project.add_parser(
        "resources", help="Duplicate, archive or restore project resources"
    ).add_subparsers(dest="resource_action")
    resources.add_parser("list")
    for operation in ("duplicate", "archive", "restore"):
        command = resources.add_parser(operation)
        command.add_argument("kind", choices=("skill", "agent", "workflow"))
        command.add_argument("identifier", help="Active identifier, or archive_id for restore")
        if operation == "duplicate":
            command.add_argument("--new-id", required=True)
            command.add_argument("--name")
        command.add_argument("--yes", action="store_true")
        command.add_argument("--token", help="Token from the reviewed preview")
    templates = project.add_parser(
        "templates", help="Export or preview/import portable project resources"
    ).add_subparsers(dest="template_action", required=True)
    export = templates.add_parser("export")
    export.add_argument("--name", required=True)
    export.add_argument("--output", type=Path)
    importing = templates.add_parser("import")
    importing.add_argument("file", type=Path)
    importing.add_argument("--yes", action="store_true")
    importing.add_argument("--token", help="Token returned by the reviewed preview")
    native_parser = group.add_parser("native")
    native_parser.add_argument("--compact", action="store_true", help="Emit compact JSON")
    native = native_parser.add_subparsers(dest="action", required=True)
    start = native.add_parser("start")
    start.add_argument(
        "kind", help="Identificador del workflow: fix, feature o uno propio del catálogo"
    )
    start.add_argument("--task", required=True)
    start.add_argument("--tool", choices=("codex", "opencode"), required=True)
    for name in ("next", "status", "pause", "resume", "retry", "finish", "cancel"):
        command = native.add_parser(name)
        command.add_argument("flow_id")
        if name == "next":
            command.add_argument("--approve-plan", action="store_true")
            command.add_argument("--approve-final", action="store_true")
            command.add_argument("--confirm-manual", action="store_true")
            command.add_argument("--confirm-external-impact", action="store_true")
            command.add_argument("--tool", choices=("codex", "opencode"))
        if name == "cancel":
            command.add_argument("--yes", action="store_true")
    return parser


def _run_config(args, root: Path) -> int:
    from factoria.application.config_recovery import (
        config_status,
        preview_config,
        apply_config,
    )

    action = args.config_action
    result = (
        config_status(root)
        if action == "status"
        else apply_config(
            root,
            action,
            identifier=getattr(args, "backup_id", None),
            token=args.token,
            confirmed=True,
        )
        if args.yes
        else preview_config(root, action, getattr(args, "backup_id", None))
    )
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 1 if result.get("conflicts") or result.get("error") else 0


def _run_relations(args, root: Path) -> int:
    from factoria.application.project_relations import project_relations

    result = project_relations(root)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return (
        1
        if not result["consistent"] or any(d["severity"] == "error" for d in result["diagnostics"])
        else 0
    )


def _run_resources(args, root: Path) -> int:
    from factoria.application.resource_lifecycle import (
        resource_inventory,
        preview_resource,
        apply_resource,
    )

    if args.resource_action in (None, "list"):
        result = resource_inventory(root)
    else:
        request = {
            "action": args.resource_action,
            "kind": args.kind,
            "archive_id" if args.resource_action == "restore" else "id": args.identifier,
        }
        if args.resource_action == "duplicate":
            request.update(new_id=args.new_id, name=args.name)
        result = (
            apply_resource(root, request, token=args.token, confirmed=True)
            if args.yes
            else preview_resource(root, request)
        )
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 1 if result.get("blockers") else 0


def _run_templates(args, root: Path) -> int:
    from factoria.application.project_templates import (
        export_template,
        read_template,
        preview_template,
        apply_template,
    )

    if args.template_action == "export":
        result = export_template(root, args.name)
        if args.output:
            from factoria.application.governance import (
                ExecutionGovernor,
                GovernedAction,
            )
            from factoria.application.policy_runtime import build_execution_context

            ExecutionGovernor().assert_allowed(GovernedAction.WRITE, build_execution_context(root))
            with args.output.open("xb") as stream:
                stream.write(
                    (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
                )
            result = {"exported": str(args.output)}
    else:
        data = read_template(args.file)
        result = (
            apply_template(root, data, expected_token=args.token, confirmed=True)
            if args.yes
            else preview_template(root, data)
        )
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 1 if result.get("conflicts") else 0


def _run_integration(args, root: Path) -> int:
    service = ProjectIntegration(root)
    if args.action == "workflows":
        from factoria.application.workflow_presets import load_catalog

        result = {
            "workflows": [
                {
                    "id": item.identifier,
                    "name": item.name or item.identifier,
                    "kind": item.kind,
                    "description": item.description,
                }
                for item in load_catalog(root).values()
            ]
        }
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    if args.action == "check":
        result = service.check()
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0 if result["ready"] else 1
    plan = service.apply(confirmed=True) if args.yes else service.plan()
    result = {
        "applied": args.yes,
        "changed": plan.changed,
        "conflicts": plan.conflicts,
        "next": "Guardar los cambios del proyecto en Git y abrir Codex u OpenCode.",
    }

    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


def _run_native(args, root: Path) -> int:
    workflow = NativeWorkflow(root)
    if args.action == "start":
        result = workflow.start(args.kind, args.task, args.tool)
    elif args.action == "next":
        result = workflow.next(
            args.flow_id,
            approve_plan=args.approve_plan,
            approve_final=args.approve_final,
            confirm_manual=args.confirm_manual,
            confirm_external_impact=args.confirm_external_impact,
            tool=args.tool,
        )
    elif args.action in {"status", "retry"}:
        result = getattr(workflow, args.action)(args.flow_id)
    else:
        result = workflow.lifecycle(
            args.flow_id, args.action, confirmed=getattr(args, "yes", False)
        )

    if args.compact:
        print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    else:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


def run_project_cli(argv: list[str]) -> int:
    args = build_project_parser().parse_args(argv)
    try:
        root = Path(args.project).expanduser().resolve()
        located = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if located.returncode != 0:
            raise ValueError("Selecciona una carpeta dentro de un repositorio Git")
        root = Path(located.stdout.strip()).resolve()
        if args.profile:
            raise ValueError(
                "El modo directo usa la política del proyecto; no cambia perfiles por ejecución"
            )
        if (
            args.read_only
            and args.command == "project"
            and args.action == "templates"
            and getattr(args, "output", None)
        ):
            raise PermissionError("Modo solo lectura: exportar a archivo está bloqueado")
        if (
            args.read_only
            and not (
                args.command == "project"
                and (args.action in {"check", "workflows"} or not getattr(args, "yes", False))
            )
            and not (args.command == "native" and args.action == "status")
        ):
            raise PermissionError("Modo solo lectura: operación bloqueada")
        if args.command == "project":
            handlers = {
                "config": _run_config,
                "relations": _run_relations,
                "resources": _run_resources,
                "templates": _run_templates,
            }
            return handlers.get(args.action, _run_integration)(args, root)
        return _run_native(args, root)
    except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=True), file=sys.stderr)
        return 1
