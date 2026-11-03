from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from factoria.application.status import OperationalStatusService
from factoria.security import SecretIncidentStore, SecretScanner
from factoria.ui_cli import TerminalUI, _slug, build_parser
from factoria.ui_workspace import UiWorkspaceSettings, choose_folder, discover_projects


class ManagedTerminalUI(TerminalUI):
    def __init__(self, root: Path, **kwargs) -> None:
        settings = UiWorkspaceSettings.load()
        preferred = settings.last_project
        if preferred and preferred.is_dir():
            root = preferred
        super().__init__(root, **kwargs)
        self.workspace_settings = settings

    def _state_path(self) -> Path:
        return Path.home() / ".factoria" / "ui-state.json"

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
            else:
                self.output("Opción no válida.")

    def run_onboarding(self) -> int:
        self.output("\n=== BIENVENIDO A FACTORIA ===")
        self.output(
            "Factoria coordina agentes de código con memoria, permisos, verificación, review y trazabilidad. "
            "Tú sigues controlando las aprobaciones."
        )

        self.output("\n1/5 · Organiza tus proyectos")
        self.output("  Factoria puede recordar una carpeta raíz para mantener todos tus repositorios juntos.")
        self._configure_projects_root(force=self.workspace_settings.projects_root is None)
        self._select_project(interactive=True)
        self._continue()

        self.output("\n2/5 · Cómo pensar en Factoria")
        self.output("  feature: plan explícito → aprobación → implementación → review → aprobación final")
        self.output("  fix pequeño: explorar → implementar → verificar → review")
        self.output("  commit: siempre se previsualiza y requiere confirmación explícita")
        self.output("  push/PR: siguen siendo manuales por diseño")
        self._continue()

        self.output("\n3/5 · Memoria del proyecto")
        if not self._is_git_project():
            self.output("  No hay un repositorio Git seleccionado todavía; este paso se puede hacer después.")
        elif (self.root / "AGENTS.md").exists():
            self.output("  ✓ Este repositorio ya tiene memoria Factoria.")
        elif self.read_only:
            self.output("  La memoria no está inicializada y --read-only impide crearla.")
        else:
            self.output("  La memoria permite a los agentes conocer estructura, reglas y verificaciones confirmadas.")
            if self._confirm("¿Quieres preparar ahora la memoria inicial?", default=True):
                name = self.input(f"Nombre del proyecto [{self.root.name}]: ").strip() or self.root.name
                purpose = self.input("Propósito breve del proyecto (opcional): ").strip()
                if self._confirm("¿Confirmas ejecutar memoria-init --yes?", default=False):
                    args = ["memoria-init", "--name", name, "--yes"]
                    if purpose:
                        args.extend(["--purpose", purpose])
                    code = self._run_command(args)
                    if code == 0:
                        self.output("Memoria creada. Revísala y haz commit antes de iniciar un flujo.")
        self._continue()

        self.output("\n4/5 · Herramientas y entorno")
        if shutil.which("git") is None:
            self.output("  ⚠ Git no está disponible en PATH. Instálalo antes de ejecutar features/fixes.")
        else:
            self.output("  ✓ Git está disponible.")
        self.output("  Codex/OpenCode se diagnostican sin relajar las políticas del núcleo.")
        if self._confirm("¿Ejecutar ahora el diagnóstico seguro de instalación?", default=True):
            self._run_command(["install", "--check-only"])
        self._continue()

        self.output("\n5/5 · Tu primer flujo")
        self.output("  1. Selecciona o crea un proyecto Git desde la opción 9.")
        self.output("  2. Mantén main limpio y elige Nueva feature o Nuevo fix.")
        self.output("  3. Factoria crea una rama y mantiene las aprobaciones explícitas.")
        self.output("  4. Revisa el resultado y confirma el commit cuando esté listo.")
        self._save_onboarding_complete()
        self.output("\n✓ Onboarding completado. Entrando al dashboard…")
        return 0

    def _render_dashboard(self) -> None:
        self.output("\n" + "=" * 64)
        self.output(" FACTORIA · MVP")
        self.output("=" * 64)
        projects_root = self.workspace_settings.projects_root
        self.output(f"Carpeta proyectos: {projects_root or 'sin configurar'}")

        if shutil.which("git") is None:
            self.output(f"Proyecto : {self.root if self._is_git_project() else 'ninguno seleccionado'}")
            self.output("Git      : NO DISPONIBLE")
            self.output("\nAviso: Git no está instalado o no está en PATH. El dashboard sigue disponible, ")
            self.output("pero features, fixes, historial y commits requieren Git.")
            return

        if not self._is_git_project():
            self.output("Proyecto : ninguno seleccionado")
            self.output("Git      : disponible")
            self.output("\nSelecciona o crea un repositorio con la opción 9.")
            return

        try:
            report = OperationalStatusService().inspect(self.root, include_history=False)
        except (OSError, subprocess.CalledProcessError, RuntimeError, ValueError) as exc:
            self.output(f"Proyecto : {self.root.name}")
            self.output("Estado   : diagnóstico parcial")
            self.output(f"Aviso    : {type(exc).__name__}: {exc}")
            self.output("\nEl dashboard permanece operativo. Usa la opción 9 para cambiar de proyecto o revisa Git.")
            return

        open_incidents = ()
        try:
            scanner = SecretScanner()
            incidents = SecretIncidentStore(self.root)
            changed = scanner.changed_paths(self.root)
            incidents.record(scanner.scan_files(self.root, changed))
            open_incidents = incidents.open()
        except (OSError, subprocess.CalledProcessError):
            self.output("Aviso    : no se pudo refrescar el escaneo incremental de secretos.")

        clean = "limpio" if not report.dirty else "cambios pendientes"
        memory = "lista" if report.memory_initialized else "sin inicializar"
        self.output(f"Proyecto : {report.project_name}")
        self.output(f"Ruta     : {self.root}")
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

    def _start_flow(self, kind: str) -> None:
        if self._require_git_project():
            super()._start_flow(kind)

    def _resume_flow(self) -> None:
        if self._require_git_project():
            super()._resume_flow()

    def _commit_flow(self) -> None:
        if self._require_git_project():
            super()._commit_flow()

    def _is_git_project(self) -> bool:
        return self.root.is_dir() and (self.root / ".git").exists()

    def _require_git_project(self) -> bool:
        if shutil.which("git") is None:
            self.output("Git no está disponible en PATH. Instálalo y vuelve a abrir Factoria.")
            self._pause()
            return False
        if not self._is_git_project():
            self.output("No hay un proyecto Git seleccionado. Usa la opción 9.")
            self._pause()
            return False
        return True

    def _ensure_project_context(self) -> None:
        if self.workspace_settings.projects_root is None:
            self._configure_projects_root(force=True)
        last = self.workspace_settings.last_project
        if last and last.is_dir() and (last / ".git").exists():
            self.root = last.resolve()
            return
        if not self._is_git_project():
            self._select_project(interactive=False)

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
                self._create_project()
            elif choice == "3":
                self._configure_projects_root(force=True)
                self._select_project(interactive=True)
            else:
                self.output("Selección no válida.")

    def _configure_projects_root(self, *, force: bool) -> None:
        current = self.workspace_settings.projects_root
        if current and not force:
            return
        self.output("\nSelecciona la carpeta donde quieres guardar/organizar todos tus proyectos.")
        selected = choose_folder(current)
        if selected is None:
            raw = self.input(
                f"Ruta de la carpeta de proyectos [{current or Path.home() / 'Projects'}]: "
            ).strip()
            selected = Path(raw).expanduser().resolve() if raw else (current or Path.home() / "Projects").resolve()
        try:
            selected.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.output(f"No se pudo usar esa carpeta: {exc}")
            return
        self.workspace_settings = UiWorkspaceSettings(
            projects_root=selected,
            last_project=self.workspace_settings.last_project,
        )
        self.workspace_settings.save()
        self.output(f"✓ Carpeta de proyectos guardada: {selected}")

    def _create_project(self) -> None:
        projects_root = self.workspace_settings.projects_root
        if projects_root is None:
            self._configure_projects_root(force=True)
            projects_root = self.workspace_settings.projects_root
        if projects_root is None:
            return
        if shutil.which("git") is None:
            self.output("No se puede crear un proyecto Factoria sin Git disponible en PATH.")
            return

        self.output("\nCrear proyecto nuevo")
        name = self.input("Nombre del proyecto: ").strip()
        if not name:
            self.output("Nombre obligatorio.")
            return
        folder_name = _slug(name)
        target = (projects_root / folder_name).resolve()
        try:
            target.relative_to(projects_root.resolve())
        except ValueError:
            self.output("Ruta de proyecto no válida.")
            return
        if target.exists():
            self.output(f"Ya existe una carpeta para ese proyecto: {target}")
            return
        purpose = self.input("Descripción breve (opcional): ").strip()
        self.output(f"\nSe creará: {target}")
        self.output("Acciones: crear carpeta, `git init -b main` y README.md inicial.")
        if not self._confirm("¿Confirmas crear el proyecto?", default=True):
            self.output("Proyecto no creado.")
            return

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
                return
            readme = f"# {name}\n"
            if purpose:
                readme += f"\n{purpose}\n"
            (target / "README.md").write_text(readme, encoding="utf-8")
        except OSError as exc:
            shutil.rmtree(target, ignore_errors=True)
            self.output(f"No se pudo crear el proyecto: {exc}")
            return

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
        self.output("Siguiente paso recomendado: inicializar/revisar la memoria Factoria antes del primer flujo.")

    def _select_project(self, *, interactive: bool) -> None:
        projects_root = self.workspace_settings.projects_root
        if projects_root is None:
            return
        projects_root = projects_root.resolve()
        projects = discover_projects(projects_root)
        if not projects:
            self.root = projects_root
            if interactive:
                self.output("No hay repositorios Git dentro de esa carpeta todavía. Puedes crear uno desde Gestión de proyectos.")
            return
        if not interactive and len(projects) == 1:
            self._remember_project(projects[0])
            return
        if not interactive:
            return

        filtered = projects
        page = 0
        page_size = 10
        while True:
            total_pages = max(1, (len(filtered) + page_size - 1) // page_size)
            page = min(page, total_pages - 1)
            start = page * page_size
            visible = filtered[start : start + page_size]
            self.output(f"\nProyectos encontrados: {len(projects)} · mostrando {len(filtered)} · página {page + 1}/{total_pages}")
            for offset, project in enumerate(visible, start=1):
                relative = project.relative_to(projects_root) if project != projects_root else Path(".")
                self.output(f"  {offset}. {project.name} · {relative}")
            self.output("\n  n = siguiente · p = anterior · /texto = buscar · / = quitar filtro · 0 = cancelar")
            raw = self.input("Selecciona proyecto: ").strip()
            if not raw or raw == "0":
                return
            if raw.lower() == "n":
                if page + 1 < total_pages:
                    page += 1
                else:
                    self.output("Ya estás en la última página.")
                continue
            if raw.lower() == "p":
                if page > 0:
                    page -= 1
                else:
                    self.output("Ya estás en la primera página.")
                continue
            if raw.startswith("/"):
                query = raw[1:].strip().lower()
                filtered = (
                    tuple(
                        project
                        for project in projects
                        if query in project.name.lower() or query in str(project.relative_to(projects_root)).lower()
                    )
                    if query
                    else projects
                )
                page = 0
                if not filtered:
                    self.output("No hay proyectos que coincidan con esa búsqueda.")
                    filtered = projects
                continue
            try:
                selected = visible[int(raw) - 1]
            except (ValueError, IndexError):
                self.output("Selección no válida.")
                continue
            self._remember_project(selected)
            return

    def _remember_project(self, selected: Path) -> None:
        projects_root = self.workspace_settings.projects_root
        self.root = selected.resolve()
        self.workspace_settings = UiWorkspaceSettings(
            projects_root=projects_root,
            last_project=self.root,
        )
        self.workspace_settings.save()
        self.output(f"✓ Proyecto seleccionado: {self.root.name}")


def run_managed_ui_cli(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.project).expanduser().resolve()
    if not root.is_dir():
        parser.error(f"Project root does not exist: {root}")
    ui = ManagedTerminalUI(root, read_only=args.read_only)
    if args.command == "onboarding":
        code = ui.run_onboarding()
        if code != 0:
            return code
        return ui.run()
    return ui.run()
