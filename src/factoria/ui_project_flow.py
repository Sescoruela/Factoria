from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from factoria.ui_app import ManagedTerminalUI
from factoria.ui_cli import _slug, build_parser
from factoria.ui_workspace import UiWorkspaceSettings


class ProjectFlowTerminalUI(ManagedTerminalUI):
    """Managed UI with a direct project-creation -> preparation -> dashboard flow."""

    def _manage_projects(self) -> None:
        while True:
            self.output("\nGestión de proyectos")
            self.output(f"Carpeta raíz actual: {self.workspace_settings.projects_root or 'sin configurar'}")
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
            subprocess.run(["git", "-C", str(target), "add", "README.md"], check=False, capture_output=True)
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
        self.workspace_settings = UiWorkspaceSettings(projects_root=projects_root, last_project=target)
        self.workspace_settings.save()
        self.output(f"✓ Proyecto creado y seleccionado: {name} · {target}")

        if self._confirm("¿Quieres preparar ahora el proyecto para trabajar con Factoria?", default=True):
            self._prepare_project_memory(name=name, purpose=purpose)
        else:
            self.output("Memoria Factoria pendiente. Podrás inicializarla más adelante desde el dashboard/onboarding.")

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
            self.output("✓ Memoria Factoria preparada. Revísala antes del primer flujo y haz commit cuando esté lista.")
            return True
        self.output("⚠ No se pudo completar memoria-init. El proyecto sigue seleccionado y puedes reintentarlo después.")
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
