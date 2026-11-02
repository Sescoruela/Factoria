from __future__ import annotations

import json
import os
from pathlib import Path

from factoria.application.setup import SetupService
from factoria.ui_project_flow import ProjectFlowTerminalUI

_AGENT_PATHS_FILE = Path.home() / ".factoria" / "agent-paths.json"


def _load_agent_paths() -> dict[str, str]:
    if not _AGENT_PATHS_FILE.exists():
        return {}
    try:
        data = json.loads(_AGENT_PATHS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        str(name): str(value)
        for name, value in data.items()
        if name in {"codex", "opencode"} and isinstance(value, str) and value.strip()
    }


def _save_agent_paths(paths: dict[str, str]) -> None:
    _AGENT_PATHS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _AGENT_PATHS_FILE.write_text(
        json.dumps(paths, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _apply_agent_paths() -> dict[str, str]:
    paths = _load_agent_paths()
    current = os.environ.get("PATH", "")
    entries = current.split(os.pathsep) if current else []
    for raw in paths.values():
        parent = str(Path(raw).expanduser().resolve().parent)
        if parent not in entries:
            entries.insert(0, parent)
    os.environ["PATH"] = os.pathsep.join(entries)
    return paths


class AgentAwareTerminalUI(ProjectFlowTerminalUI):
    """Project UI that makes coding-agent discovery/configuration visible and actionable."""

    def __init__(self, root: Path, **kwargs) -> None:
        self.agent_paths = _apply_agent_paths()
        super().__init__(root, **kwargs)

    def run(self) -> int:
        if not self._onboarding_complete():
            self.output("\nPrimera ejecución de la UI de Factoria.")
            if self._confirm("¿Quieres hacer el onboarding guiado ahora?", default=True):
                self.run_onboarding()

        self._ensure_project_context()
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
            self.output("  9. Gestionar proyectos")
            if self._is_git_project() and not (self.root / "AGENTS.md").exists() and not self.read_only:
                self.output("  M. Inicializar memoria del proyecto")
            if not self.read_only:
                self.output("  A. Configurar Codex / OpenCode")
            self.output("  H. Ver todos los comandos disponibles")
            self.output("  0. Salir")
            self.output("\nTambién puedes escribir directamente un comando, por ejemplo: status")
            raw_choice = self.input("\nElige una opción o escribe un comando: ").strip()
            choice = raw_choice.lower()
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
                if self._require_git_project():
                    self._run_command(["history", "--limit", "10"])
                    self._pause()
            elif choice == "6":
                if self._require_git_project():
                    self._security()
            elif choice == "7":
                self.run_onboarding()
            elif choice == "8":
                continue
            elif choice == "9":
                self._manage_projects()
            elif choice == "m" and self._is_git_project() and not (self.root / "AGENTS.md").exists() and not self.read_only:
                self._initialize_memory_from_dashboard()
            elif choice == "a" and not self.read_only:
                self._configure_agents()
                self._pause()
            elif choice in {"h", "help", "ayuda", "comandos"}:
                self._show_command_help()
                self._pause()
            elif raw_choice:
                self._execute_console_command(raw_choice)
                self._pause()
            else:
                self.output("Opción no válida.")

    def _render_dashboard(self) -> None:
        super()._render_dashboard()
        self.output("\nAgentes de código")
        try:
            statuses = SetupService().inspect_tools()
        except Exception as exc:
            self.output(f"  No se pudo diagnosticar Codex/OpenCode: {type(exc).__name__}: {exc}")
            return
        for status in statuses:
            if status.passed:
                state = "LISTO"
            elif status.available:
                state = "DETECTADO · diagnóstico pendiente/fallido"
            else:
                state = "NO DETECTADO"
            persisted = self.agent_paths.get(status.name)
            source = f" · ruta configurada: {persisted}" if persisted else ""
            self.output(f"  {status.name:<8}: {state}{source}")
        self.output("  Autenticación: Factoria no afirma login/conexión; valida compatibilidad local del CLI.")

    def _configure_agents(self) -> None:
        self.output("\nConfiguración de agentes")
        statuses = SetupService().inspect_tools()
        for index, status in enumerate(statuses, start=1):
            failed = [check.name for check in status.checks if check.required and not check.passed]
            if status.passed:
                state = "listo"
            elif status.available:
                state = "detectado, pero no listo"
            else:
                state = "no detectado"
            self.output(f"  {index}. {status.name}: {state}")
            if failed:
                self.output("     Fallos: " + ", ".join(failed))
        self.output("  P. Indicar ruta de un ejecutable Codex/OpenCode")
        self.output("  D. Ejecutar diagnóstico detallado")
        self.output("  0. Volver")
        raw = self.input("Selección: ").strip().lower()
        if raw == "0":
            return
        if raw == "d":
            self._run_command(["install", "--check-only"])
            return
        if raw == "p":
            self._configure_agent_path()
            return
        try:
            selected = statuses[int(raw) - 1]
        except (ValueError, IndexError):
            self.output("Selección no válida.")
            return
        if not selected.passed:
            self.output(
                f"{selected.name} todavía no está listo. Usa D para ver el diagnóstico o P para indicar su ruta."
            )
            return
        if not self._confirm(f"¿Usar {selected.name} como agente predeterminado?", default=True):
            return
        code = self._run_command(["install", "--default-tool", selected.name, "--yes"])
        if code == 0:
            self.output(f"✓ {selected.name} configurado como agente predeterminado.")
        else:
            self.output(f"No se pudo configurar {selected.name}; revisa el diagnóstico.")

    def _configure_agent_path(self) -> None:
        name = self.input("Herramienta [codex/opencode]: ").strip().lower()
        if name not in {"codex", "opencode"}:
            self.output("Herramienta no válida.")
            return
        raw = self.input("Ruta completa al ejecutable (.exe/.cmd): ").strip().strip('"')
        if not raw:
            return
        executable = Path(raw).expanduser().resolve()
        if not executable.is_file():
            self.output(f"No existe ese ejecutable: {executable}")
            return
        paths = dict(self.agent_paths)
        paths[name] = str(executable)
        _save_agent_paths(paths)
        self.agent_paths = paths
        parent = str(executable.parent)
        entries = os.environ.get("PATH", "").split(os.pathsep)
        if parent not in entries:
            os.environ["PATH"] = os.pathsep.join([parent, *entries])
        self.output(f"✓ Ruta de {name} guardada para Factoria: {executable}")
        status = next(item for item in SetupService().inspect_tools() if item.name == name)
        if status.passed:
            self.output(f"✓ {name} ya pasa las comprobaciones de compatibilidad de Factoria.")
        elif status.available:
            self.output(f"⚠ {name} se detecta, pero alguna comprobación requerida sigue fallando.")
        else:
            self.output(
                f"⚠ La ruta se guardó, pero Factoria aún no localiza el comando {name!r}. "
                "Comprueba que el ejecutable tenga ese nombre o usa el diagnóstico detallado."
            )


def run_agent_aware_ui_cli(argv: list[str]) -> int:
    from factoria.ui_cli import build_parser

    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.project).expanduser().resolve()
    if not root.is_dir():
        parser.error(f"Project root does not exist: {root}")
    ui = AgentAwareTerminalUI(root, read_only=args.read_only)
    if args.command == "onboarding":
        code = ui.run_onboarding()
        if code != 0:
            return code
        return ui.run()
    return ui.run()
