from __future__ import annotations

import shlex
import shutil
import subprocess
from pathlib import Path

from factoria.ui_app import ManagedTerminalUI
from factoria.ui_cli import _slug, build_parser
from factoria.ui_workspace import UiWorkspaceSettings


COMMAND_HELP: tuple[tuple[str, str], ...] = (
    ("status [--all]", "Ver el estado del proyecto"),
    (
        "memoria-init [--name NOMBRE] [--purpose TEXTO] [--yes]",
        "Inicializar la memoria del proyecto",
    ),
    ("memoria-update [--yes]", "Revisar/actualizar la memoria existente"),
    ('feature "título" [--branch rama] [--tool codex|opencode]', "Iniciar una feature"),
    ('fix "título" [--branch rama] [--tool codex|opencode] [--large]', "Iniciar un fix"),
    ("resume [flow_id] [--approve-plan|--approve-final]", "Reanudar un flujo"),
    ("pause FLOW_ID [--reason texto]", "Pausar un flujo"),
    ("cancel FLOW_ID [--reason texto] [--yes]", "Cancelar un flujo"),
    ("commit [flow_id] [--yes]", "Previsualizar o confirmar un commit"),
    ("history [--limit N] [--report]", "Ver el historial local"),
    ("security incidents", "Listar incidentes de seguridad"),
    ("security resolve ID --confirm-rotation", "Resolver un incidente ya rotado/revocado"),
    ("plugins", "Listar plugins descubiertos"),
    ("install --check-only", "Diagnosticar Git/Codex/OpenCode y configuración"),
    ("update", "Comprobar una actualización de Factoria"),
    ("rollback", "Revisar/restaurar la versión anterior"),
    ("onboarding", "Repetir la guía interactiva"),
)


def _normalize_console_token(token: str) -> str:
    if len(token) >= 2 and token[0] == token[-1] and token[0] in {'"', "'"}:
        return token[1:-1]
    return token


class ProjectFlowTerminalUI(ManagedTerminalUI):
    """Managed UI with project navigation plus a safe interactive command console."""

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
                self.output("  1. Guía feature (inicio externo)")
                self.output("  2. Guía fix (inicio externo)")
                self.output("  3. Guía de reanudación externa")
                self.output("  4. Revisar / crear commit")
            self.output("  5. Historial")
            self.output("  6. Incidentes de seguridad")
            self.output("  7. Onboarding / guía")
            self.output("  8. Actualizar dashboard")
            self.output("  9. Gestionar proyectos")
            if (
                self._is_git_project()
                and not (self.root / "AGENTS.md").exists()
                and not self.read_only
            ):
                self.output("  M. Inicializar memoria del proyecto")
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
            elif (
                choice == "m"
                and self._is_git_project()
                and not (self.root / "AGENTS.md").exists()
                and not self.read_only
            ):
                self._initialize_memory_from_dashboard()
            elif choice in {"h", "help", "ayuda", "comandos"}:
                self._show_command_help()
                self._pause()
            elif raw_choice:
                self._execute_console_command(raw_choice)
                self._pause()
            else:
                self.output("Opción no válida.")

    def _show_command_help(self) -> None:
        self.output("\nComandos disponibles desde esta misma pantalla")
        self.output("Puedes escribirlos con o sin el prefijo `factoria`.")
        for command, description in COMMAND_HELP:
            if command.split()[0] in {"feature", "fix", "resume", "install"}:
                continue
            self.output(f"  {command}")
            self.output(f"    {description}")
        self.output("\nEjemplos:")
        self.output("  status")
        self.output(
            '  memoria-init --name Organizador --purpose "Organizar turnos por medias horas"'
        )

        self.output("  factoria history --limit 20")
        self.output("\nFeature/fix y reanudación: desde Codex/OpenCode, fuera de la aplicación.")
        self.output(
            "\nLas confirmaciones y políticas de seguridad siguen aplicándose igual que en el CLI."
        )

    def _execute_console_command(self, raw: str) -> None:
        try:
            args = [_normalize_console_token(item) for item in shlex.split(raw, posix=False)]
        except ValueError as exc:
            self.output(f"Comando no válido: {exc}")
            return
        if args and args[0].lower() == "factoria":
            args = args[1:]
        if not args:
            self._show_command_help()
            return

        command = args[0].lower()
        if command == "ui":
            self.output("Ya estás dentro de la UI de Factoria.")
            return
        if command == "onboarding":
            self.run_onboarding()
            return
        if command in {"help", "ayuda", "comandos"}:
            self._show_command_help()
            return

        try:
            self._run_command(args)
        except SystemExit as exc:
            if exc.code not in {None, 0}:
                self.output(
                    "El comando no se pudo interpretar. Escribe H para ver ejemplos y comandos disponibles."
                )
        except (OSError, RuntimeError, ValueError, PermissionError) as exc:
            self.output(f"El comando no pudo completarse: {exc}")

    def _render_dashboard(self) -> None:
        original_output = self.output

        def translated_output(line: str) -> None:
            if line.strip() == "Run `factoria memoria-init` and review the proposal.":
                original_output("  Inicializa la memoria del proyecto antes del primer flujo.")
                return
            original_output(line)

        self.output = translated_output
        try:
            super()._render_dashboard()
        finally:
            self.output = original_output

    def _initialize_memory_from_dashboard(self) -> None:
        if not self._require_git_project():
            return
        if (self.root / "AGENTS.md").exists():
            self.output("La memoria Factoria ya está inicializada.")
            return
        name = self.input(f"Nombre del proyecto [{self.root.name}]: ").strip() or self.root.name
        purpose = self.input("Propósito breve del proyecto (opcional): ").strip()
        if not self._confirm("¿Confirmas preparar la memoria Factoria ahora?", default=True):
            self.output("Inicialización cancelada.")
            return
        self._prepare_project_memory(name=name, purpose=purpose)

    def _manage_projects(self) -> None:
        while True:
            self.output("\nGestión de proyectos")
            self.output(
                f"Carpeta raíz actual: {self.workspace_settings.projects_root or 'sin configurar'}"
            )
            self.output("  1. Seleccionar proyecto")
            if not self.read_only:
                self.output("  2. Crear proyecto nuevo")
                self.output("  3. Cambiar carpeta raíz de proyectos")
            else:
                self.output("  3. Cambiar carpeta raíz de proyectos")
            self.output("  0. Volver")
            choice = self.input("Selección: ").strip()
            if choice == "0":
                return
            if choice == "1":
                self._select_project(interactive=True)
            elif choice == "2" and not self.read_only:
                if self._create_project_and_prepare():
                    return
            elif choice == "3":
                self._configure_projects_root(force=True)
                self._select_project(interactive=True)
            else:
                self.output("Selección no válida.")

    def _create_project_and_prepare(self) -> bool:
        projects_root = self.workspace_settings.projects_root
        if projects_root is None:
            self._configure_projects_root(force=True)
            projects_root = self.workspace_settings.projects_root
        if projects_root is None:
            return False
        if shutil.which("git") is None:
            self.output("No se puede crear un proyecto Factoria sin Git disponible en PATH.")
            return False

        self.output("\nCrear proyecto nuevo")
        name = self.input("Nombre del proyecto: ").strip()
        if not name:
            self.output("Nombre obligatorio.")
            return False
        folder_name = _slug(name)
        target = (projects_root / folder_name).resolve()
        try:
            target.relative_to(projects_root.resolve())
        except ValueError:
            self.output("Ruta de proyecto no válida.")
            return False
        if target.exists():
            self.output(f"Ya existe una carpeta para ese proyecto: {target}")
            return False

        purpose = self.input("Descripción breve (opcional): ").strip()
        self.output(f"\nSe creará: {target}")
        self.output("Acciones: crear carpeta, `git init -b main` y README.md inicial.")
        if not self._confirm("¿Confirmas crear el proyecto?", default=True):
            self.output("Proyecto no creado.")
            return False

        try:
            target.mkdir(parents=False)
            completed = subprocess.run(
                ["git", "init", "-b", "main", str(target)],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if completed.returncode != 0:
                shutil.rmtree(target, ignore_errors=True)
                details = completed.stderr.strip() or completed.stdout.strip() or "git init falló"
                self.output(f"No se pudo inicializar Git: {details}")
                return False
            readme = f"# {name}\n"
            if purpose:
                readme += f"\n{purpose}\n"
            (target / "README.md").write_text(readme, encoding="utf-8")
        except OSError as exc:
            shutil.rmtree(target, ignore_errors=True)
            self.output(f"No se pudo crear el proyecto: {exc}")
            return False

        if self._confirm("¿Crear también el commit inicial con README.md?", default=True):
            subprocess.run(
                ["git", "-C", str(target), "add", "README.md"], check=False, capture_output=True
            )
            committed = subprocess.run(
                ["git", "-C", str(target), "commit", "-m", "Initial commit"],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if committed.returncode != 0:
                self.output("⚠ Proyecto creado, pero no se pudo hacer el commit inicial.")
                self.output("  Revisa que Git tenga configurados user.name y user.email.")

        self.root = target
        self.workspace_settings = UiWorkspaceSettings(
            projects_root=projects_root, last_project=target
        )
        self.workspace_settings.save()
        self.output(f"✓ Proyecto creado y seleccionado: {name} · {target}")

        if self._confirm(
            "¿Quieres preparar ahora el proyecto para trabajar con Factoria?", default=True
        ):
            self._prepare_project_memory(name=name, purpose=purpose)
        else:
            self.output(
                "Memoria Factoria pendiente. Podrás inicializarla más adelante desde el dashboard."
            )

        self.output("Volviendo al dashboard del proyecto…")
        return True

    def _prepare_project_memory(self, *, name: str, purpose: str) -> bool:
        if (self.root / "AGENTS.md").exists():
            self.output("✓ La memoria Factoria ya está inicializada.")
            return True
        if self.read_only:
            self.output("--read-only impide inicializar la memoria del proyecto.")
            return False

        args = ["memoria-init", "--name", name, "--yes"]
        if purpose:
            args.extend(["--purpose", purpose])
        code = self._run_command(args)
        if code == 0:
            self.output(
                "✓ Memoria Factoria preparada. Revísala antes del primer flujo y haz commit cuando esté lista."
            )
            return True
        self.output(
            "⚠ No se pudo completar memoria-init. El proyecto sigue seleccionado y puedes reintentarlo después."
        )
        return False


def run_project_flow_ui_cli(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.project).expanduser().resolve()
    if not root.is_dir():
        parser.error(f"Project root does not exist: {root}")
    ui = ProjectFlowTerminalUI(root, read_only=args.read_only)
    if args.command == "onboarding":
        code = ui.run_onboarding()
        if code != 0:
            return code
        return ui.run()
    return ui.run()
