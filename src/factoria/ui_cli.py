from __future__ import annotations

import argparse
import json
import re
import subprocess
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from factoria.application.artifacts import FlowArtifactStore
from factoria.application.state_store import LocalFlowStateStore
from factoria.application.status import OperationalStatusService
from factoria.security import SecretIncidentStore, SecretScanner

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]
CommandRunner = Callable[[list[str]], int]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="factoria")
    parser.add_argument("--project", default=".", help="Project root (default: current directory)")
    parser.add_argument("--read-only", action="store_true", help="Disable actions that modify project or flow state")
    parser.add_argument("--profile", help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ui", help="Open the interactive Factoria terminal UI")
    sub.add_parser("onboarding", help="Run or repeat the guided Factoria onboarding")
    return parser


class TerminalUI:
    def __init__(
        self,
        root: Path,
        *,
        read_only: bool = False,
        input_fn: InputFn = input,
        output_fn: OutputFn = print,
        command_runner: CommandRunner | None = None,
    ) -> None:
        self.root = root.resolve()
        self.read_only = read_only
        self.input = input_fn
        self.output = output_fn
        self.command_runner = command_runner or self._default_command_runner

    def run(self) -> int:
        if not self._onboarding_complete():
            self.output("\nPrimera ejecución de la UI de Factoria.")
            if self._confirm("¿Quieres hacer el onboarding guiado ahora?", default=True):
                self.run_onboarding()

        while True:
            self._render_dashboard()
            self.output("\nAcciones")
            if not self.read_only:
                self.output("  1. Nueva feature")
                self.output("  2. Nuevo fix")
                self.output("  3. Reanudar flujo")
                self.output("  4. Revisar / crear commit")
            self.output("  5. Historial")
            self.output("  6. Incidentes de seguridad")
            self.output("  7. Onboarding / guía")
            self.output("  8. Actualizar dashboard")
            self.output("  0. Salir")
            choice = self.input("\nElige una opción: ").strip()
            if choice == "0":
                self.output("Hasta la próxima.")
                return 0
            if choice == "1" and not self.read_only:
                self._start_flow("feature")
            elif choice == "2" and not self.read_only:
                self._start_flow("fix")
            elif choice == "3" and not self.read_only:
                self._resume_flow()
            elif choice == "4" and not self.read_only:
                self._commit_flow()
            elif choice == "5":
                self._run_command(["history", "--limit", "10"])
                self._pause()
            elif choice == "6":
                self._security()
            elif choice == "7":
                self.run_onboarding()
            elif choice == "8":
                continue
            else:
                self.output("Opción no válida.")

    def run_onboarding(self) -> int:
        self.output("\n=== BIENVENIDO A FACTORIA ===")
        self.output(
            "Factoria coordina agentes de código con memoria del proyecto, permisos, "
            "verificación, review y trazabilidad. Tú sigues controlando las aprobaciones."
        )
        self.output("\n1/4 · Cómo pensar en Factoria")
        self.output("  feature: plan explícito → aprobación → implementación → review → aprobación final")
        self.output("  fix pequeño: explorar → implementar → verificar → review")
        self.output("  commit: siempre se previsualiza y requiere confirmación explícita")
        self.output("  push/PR: siguen siendo manuales por diseño")
        self._continue()

        self.output("\n2/4 · Memoria del proyecto")
        if (self.root / "AGENTS.md").exists():
            self.output("  ✓ Este repositorio ya tiene memoria Factoria.")
        elif self.read_only:
            self.output("  - La memoria no está inicializada y --read-only impide crearla.")
            self.output("    Ejecuta después: factoria memoria-init --yes")
        else:
            self.output("  La memoria permite a los agentes conocer estructura, reglas y verificaciones confirmadas.")
            if self._confirm("¿Quieres preparar ahora la memoria inicial?", default=True):
                name = self.input(f"Nombre del proyecto [{self.root.name}]: ").strip() or self.root.name
                purpose = self.input("Propósito breve del proyecto (opcional): ").strip()
                self.output("\nFactoria mostrará/propondrá la memoria y la escribirá solo porque la estás confirmando aquí.")
                if self._confirm("¿Confirmas ejecutar memoria-init --yes?", default=False):
                    args = ["memoria-init", "--name", name, "--yes"]
                    if purpose:
                        args.extend(["--purpose", purpose])
                    code = self._run_command(args)
                    if code == 0:
                        self.output(
                            "Memoria creada. Revísala y haz un commit Git antes de iniciar un flujo: "
                            "Factoria exige un árbol limpio."
                        )
                else:
                    self.output("Memoria no modificada.")
            else:
                self.output("Puedes hacerlo más tarde con `factoria memoria-init`.")
        self._continue()

        self.output("\n3/4 · Herramientas y entorno")
        self.output("  Instala, inicia y autentica Codex/OpenCode fuera de Factoría.")
        self.output("  La aplicación guarda la configuración del proyecto y no ejecuta diagnósticos de esos CLIs.")
        self._continue()

        self.output("\n4/4 · Tu primer flujo")
        self.output("  1. Configura agentes y flujos y prepara la integración del proyecto.")
        self.output("  2. Guarda la configuración en Git y selecciona una rama de trabajo limpia.")
        self.output("  3. Abre Codex u OpenCode por tu cuenta en ese proyecto.")
        self.output("  4. Pide una feature o un fix y sigue el flujo configurado desde esa herramienta.")
        self._save_onboarding_complete()
        self.output("\n✓ Onboarding completado. Puedes repetirlo en cualquier momento con `factoria onboarding`.")
        return 0

    def _render_dashboard(self) -> None:
        self.output("\n" + "=" * 64)
        self.output(" FACTORIA · MVP")
        self.output("=" * 64)
        try:
            report = OperationalStatusService().inspect(self.root, include_history=False)
            scanner = SecretScanner()
            incidents = SecretIncidentStore(self.root)
            incidents.record(scanner.scan_files(self.root, scanner.changed_paths(self.root)))
            open_incidents = incidents.open()
        except Exception as exc:  # UI should stay usable and expose diagnostics rather than crash.
            self.output(f"No se pudo cargar el dashboard: {exc}")
            return

        clean = "limpio" if not report.dirty else "cambios pendientes"
        memory = "lista" if report.memory_initialized else "sin inicializar"
        self.output(f"Proyecto : {report.project_name}")
        self.output(f"Rama     : {report.branch} · {clean}")
        self.output(f"Memoria  : {memory}")
        self.output(f"Perfil   : {report.effective_profile}")
        self.output(f"Agente   : {report.effective_tool or 'sin configurar'}")
        if open_incidents:
            self.output(f"Seguridad: BLOQUEADA · {len(open_incidents)} incidente(s) abierto(s)")
        else:
            self.output("Seguridad: sin incidentes abiertos")

        if report.active_flows:
            self.output("\nFlujo activo")
            for flow in report.active_flows:
                stage = f" · {flow.runtime_stage}" if flow.runtime_stage else ""
                branch = f" · {flow.branch}" if flow.branch else ""
                self.output(f"  {flow.flow_id[:8]} · {flow.kind} · {flow.state}{stage}{branch}")
        else:
            self.output("\nFlujo activo: ninguno")

        if report.recommendations:
            self.output("\nSiguiente recomendado")
            self.output(f"  {report.recommendations[0]}")
        if self.read_only:
            self.output("\nMODO READ-ONLY: acciones de escritura deshabilitadas")

    def _start_flow(self, kind: str) -> None:
        self.output(f"Abre Codex/OpenCode fuera de Factoría y solicita el flujo {kind} en el proyecto preparado.")

    def _resume_flow(self) -> None:
        self.output("Reanuda el flujo desde la sesión externa de Codex/OpenCode.")

    def _commit_flow(self) -> None:
        selections = self._incomplete_flows()
        if not selections:
            self.output("No hay flujos pendientes de commit.")
            self._pause()
            return
        execution = self._select_flow(selections)
        if execution is None:
            return
        flow_id = execution.flow.flow_id
        self.output("\nPrevisualización del commit:")
        code = self._run_command(["commit", flow_id])
        if code != 0:
            self.output("No se puede preparar el commit todavía.")
            self._pause()
            return
        if not self._confirm("¿Confirmas crear exactamente este commit?", default=False):
            self.output("Commit no creado.")
            return
        args = ["commit", flow_id, "--yes"]
        if self._confirm("Si había verificación manual, ¿la completaste toda?", default=False):
            args.append("--confirm-manual-verification")
        if self._confirm("Si había impacto externo, ¿revisaste los consumidores/repositorios afectados?", default=False):
            args.append("--confirm-external-impact-review")
        self._run_command(args)
        self._pause()

    def _security(self) -> None:
        self._run_command(["security", "incidents"])
        if self.read_only:
            self._pause()
            return
        if not self._confirm("¿Quieres intentar resolver un incidente ya rotado/revocado?", default=False):
            self._pause()
            return
        incident_id = self.input("ID completo del incidente: ").strip()
        if not incident_id:
            return
        self.output("Factoria solo lo resolverá si confirmas la rotación/revocación y verifica que ya no aparece.")
        if self._confirm("¿La credencial ya fue rotada o revocada fuera de Factoria?", default=False):
            self._run_command(["security", "resolve", incident_id, "--confirm-rotation"])
        self._pause()

    def _incomplete_flows(self):
        artifacts = FlowArtifactStore(self.root)
        return tuple(LocalFlowStateStore(artifacts).incomplete())

    def _select_flow(self, executions):
        for index, execution in enumerate(executions, start=1):
            self.output(
                f"  {index}. {execution.flow.flow_id[:8]} · {execution.flow.kind} · "
                f"{execution.flow.state.value} · {execution.label or '-'}"
            )
        raw = self.input("Selecciona flujo [0 cancelar]: ").strip()
        if raw in {"", "0"}:
            return None
        try:
            index = int(raw) - 1
            return executions[index] if 0 <= index < len(executions) else None
        except ValueError:
            self.output("Selección no válida.")
            return None

    def _default_command_runner(self, args: list[str]) -> int:
        from factoria.entrypoint import main

        prefix = ["--project", str(self.root)]
        if self.read_only:
            prefix.append("--read-only")
        return main(prefix + args)

    def _run_command(self, args: list[str]) -> int:
        from factoria.application.tool_presence import assert_ui_command_allowed
        try:
            assert_ui_command_allowed(args)
        except ValueError as exc:
            self.output(str(exc))
            return 1
        self.output("\n" + "─" * 64)
        return self.command_runner(args)

    def _state_path(self) -> Path:
        try:
            result = subprocess.run(
                ["git", "-C", str(self.root), "rev-parse", "--git-path", "factoria/ui-state.json"],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            path = Path(result.stdout.strip())
            return path if path.is_absolute() else self.root / path
        except (OSError, subprocess.CalledProcessError):
            return self.root / ".factoria" / "ui-state.json"

    def _onboarding_complete(self) -> bool:
        path = self._state_path()
        if not path.exists():
            return False
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        return bool(data.get("onboarding_completed"))

    def _save_onboarding_complete(self) -> None:
        path = self._state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "onboarding_completed": True,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _confirm(self, prompt: str, *, default: bool) -> bool:
        suffix = " [S/n]: " if default else " [s/N]: "
        answer = self.input(prompt + suffix).strip().lower()
        if not answer:
            return default
        return answer in {"s", "si", "sí", "y", "yes"}

    def _continue(self) -> None:
        self.input("\nPulsa Enter para continuar...")

    def _pause(self) -> None:
        self.input("\nPulsa Enter para volver al dashboard...")


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    compact = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.lower()).strip("-")
    return compact[:48] or "change"


def run_ui_cli(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.project).expanduser().resolve()
    if not root.is_dir():
        parser.error(f"Project root does not exist: {root}")
    ui = TerminalUI(root, read_only=args.read_only)
    if args.command == "onboarding":
        return ui.run_onboarding()
    return ui.run()
