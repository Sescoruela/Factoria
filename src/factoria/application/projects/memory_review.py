"""Review a source-backed memory report from an existing agent session."""

import hashlib
import json
import subprocess
from pathlib import Path

from factoria.application.governance import ExecutionGovernor, GovernedAction
from factoria.application.policy_runtime import build_execution_context
from factoria.application.projects.resource_support import catalog_locks
from factoria.git_local import ensure_local_project_files
from factoria.project_paths import project_path
from factoria.security.secrets import SecretScanner
from factoria.storage import atomic_write_bytes

REVIEW_PATH = "docs/memoria/revision.md"
_MARKER = "<!-- factoria: memory review -->"
SECTIONS = {
    "purpose": "Propósito y alcance",
    "architecture": "Arquitectura y puntos de entrada",
    "flows": "Flujos y datos",
    "contracts": "Contratos e integraciones",
    "decisions": "Decisiones y restricciones",
    "checks": "Pruebas y verificación",
}
MAX_REPORT_BYTES = 65536


def review_request() -> str:
    return (
        "Analiza el repositorio abierto para actualizar la memoria de Factoría. "
        "Trabaja en solo lectura. No ejecutes las pruebas ni modifiques archivos. "
        "Inspecciona el código, los manifiestos y la documentación pertinente. "
        "Cubre las partes reales del proyecto, incluidos sus puntos de entrada, módulos y "
        "responsabilidades, relaciones entre capas, flujos de usuario y datos, persistencia, "
        "contratos, dependencias externas, decisiones explícitas, restricciones y pruebas. "
        "Cita archivos concretos del repositorio para cada hallazgo. Los comandos declarados "
        "deben figurar como no ejecutados. No leas ni incluyas secretos o configuración privada. "
        "Indica como pendientes las áreas que no puedas confirmar, sin completar huecos por intuición. "
        "Devuelve solo JSON, sin bloque Markdown. Esquema: "
        + json.dumps(
            {
                "commit": "<SHA completo de git rev-parse HEAD>",
                **{
                    key: [{"finding": f"<{title}>", "sources": ["<ruta relativa a un archivo>"]}]
                    for key, title in SECTIONS.items()
                },
                "pending": ["<dato por confirmar>"],
            },
            ensure_ascii=False,
        )
        + ". Usa listas vacías donde no haya evidencia. Inspecciona el código actual, "
        "no copies la plantilla de AGENTS.md ni la memoria previa como única fuente."
    )


def _line(value: object, limit: int) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > limit
        or len(value.splitlines()) != 1
        or any(char in value for char in ("<", ">", "\x00"))
    ):
        raise ValueError("El informe contiene texto vacío o un formato no admitido")
    return value.strip()


def _source(root: Path, value: object) -> str:
    relative = _line(value, 350)
    if (
        "`" in relative
        or relative == "AGENTS.md"
        or relative.startswith("docs/memoria/")
        or any(part in {".git", ".factoria"} for part in relative.split("/"))
    ):
        raise ValueError("Las fuentes deben ser archivos de código o documentación del proyecto")
    path = project_path(root, relative)
    if not path.is_file() or path.relative_to(root).as_posix() != relative:
        raise ValueError(f"Fuente inexistente o ruta no canónica: {relative}")
    return relative


def _render(root: Path, report: object, commit: str) -> str:
    if not isinstance(report, dict) or set(report) != {"commit", *SECTIONS, "pending"}:
        raise ValueError("El informe debe seguir el esquema del encargo de Factoría")
    if report["commit"] != commit:
        raise ValueError("El informe corresponde a otro commit. Vuelve a analizar el proyecto.")
    lines = [_MARKER, "# Revisión del proyecto", "", f"Commit analizado: `{commit}`"]
    found = False
    for key, title in SECTIONS.items():
        entries = report[key]
        if not isinstance(entries, list) or len(entries) > 32:
            raise ValueError(f"Sección no válida: {title}")
        lines.extend(["", f"## {title}", ""])
        if not entries:
            lines.append("- Sin hallazgos con referencia para esta sección.")
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"finding", "sources"}:
                raise ValueError(f"Cada hallazgo necesita texto y fuentes: {title}")
            sources = entry["sources"]
            if not isinstance(sources, list) or not 1 <= len(sources) <= 8:
                raise ValueError(f"Cada hallazgo necesita entre 1 y 8 fuentes: {title}")
            links = ", ".join(f"`{_source(root, path)}`" for path in sources)
            lines.append(f"- {_line(entry['finding'], 1400)}")
            lines.append(f"  Fuentes: {links}")
            found = True
    if not found:
        raise ValueError("El informe debe aportar al menos un hallazgo con fuentes")
    pending = report["pending"]
    if not isinstance(pending, list) or len(pending) > 32:
        raise ValueError("La lista de datos pendientes no es válida")
    if pending:
        lines.extend(["", "## Pendiente de confirmar", ""])
        lines.extend(f"- {_line(item, 700)}" for item in pending)
    rendered = "\n".join(lines) + "\n"
    if SecretScanner().scan_text(rendered, location=REVIEW_PATH):
        raise ValueError("El informe contiene un posible secreto. Elimínalo antes de importar.")
    return rendered


def review_memory(
    root: Path, raw_report: object, *, confirmed: bool = False, token: object = None
) -> dict:
    governor = ExecutionGovernor()
    governor.assert_allowed(
        GovernedAction.WRITE if confirmed else GovernedAction.READ, build_execution_context(root)
    )
    if not isinstance(raw_report, str) or len(raw_report.encode("utf-8")) > MAX_REPORT_BYTES:
        raise ValueError("El informe debe ser texto JSON de hasta 64 KiB")
    try:
        report = json.loads(raw_report)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON no válido en la línea {exc.lineno}, columna {exc.colno}") from exc
    root = root.resolve()
    with catalog_locks():
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise ValueError("Crea el primer commit del repositorio para revisar su memoria.")
        commit = result.stdout.strip()
        markdown = _render(root, report, commit)
        target = project_path(root, REVIEW_PATH)
        existed = target.exists()
        before = target.read_bytes() if existed else b""
        if existed and not before.startswith((_MARKER + "\n").encode()):
            raise ValueError(f"Ya existe un documento propio en {REVIEW_PATH}")
        content = markdown.encode("utf-8")
        revision = hashlib.sha256(
            str(root).encode("utf-8") + b"\0" + before + b"\0" + content
        ).hexdigest()
        if confirmed:
            if token != revision:
                raise ValueError("La propuesta cambió. Vuelve a revisarla antes de guardarla.")
            ensure_local_project_files(root, (REVIEW_PATH,))
            atomic_write_bytes(target, content, create=not existed)
    return {"path": REVIEW_PATH, "markdown": markdown, "revision": revision}
