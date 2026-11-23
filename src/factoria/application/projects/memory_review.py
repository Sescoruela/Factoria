"""Review a source-backed memory report from an existing agent session."""

import hashlib
import json
import subprocess
from pathlib import Path

from factoria.application.governance import ExecutionGovernor, GovernedAction
from factoria.application.policy_runtime import build_execution_context
from factoria.application.projects.resource_support import catalog_locks
from factoria.git_local import ensure_local_project_files, tracked_project_files
from factoria.project_paths import project_path
from factoria.security.secrets import SecretScanner
from factoria.storage import atomic_write_bytes

REVIEW_PATH = "docs/memoria/revision.md"
_MARKER = "<!-- factoria: memory review -->"
_DETAIL_START = b"<!-- factoria: memory findings:start -->"
_DETAIL_END = b"<!-- factoria: memory findings:end -->"
_DETAILS = {
    "docs/memoria/arquitectura.md": ("Arquitectura", ("architecture", "contracts")),
    "docs/memoria/flujos.md": ("Flujos", ("flows",)),
    "docs/memoria/decisiones.md": ("Decisiones", ("decisions",)),
    "docs/memoria/testing.md": ("Pruebas y verificación", ("checks",)),
}
SECTIONS = {
    "purpose": "Propósito y alcance",
    "architecture": "Arquitectura y puntos de entrada",
    "flows": "Flujos y datos",
    "contracts": "Contratos e integraciones",
    "decisions": "Decisiones y restricciones",
    "checks": "Pruebas y verificación",
}
MAX_REPORT_BYTES = 65536
_MAX_SOURCES = 8
_MAX_PENDING = 32


def review_request(commit: str = "<SHA completo de git rev-parse HEAD>") -> str:
    return (
        "Analiza el repositorio abierto para actualizar la memoria de Factoría. "
        "Trabaja en solo lectura. No ejecutes las pruebas ni modifiques archivos. "
        "Inspecciona el código, los manifiestos y la documentación pertinente. "
        "Cubre las partes reales del proyecto, incluidos sus puntos de entrada, módulos y "
        "responsabilidades, relaciones entre capas, flujos de usuario y datos, persistencia, "
        "contratos, dependencias externas, decisiones explícitas, restricciones y pruebas. "
        f"Cita entre 1 y {_MAX_SOURCES} rutas relativas distintas por hallazgo. "
        "Si no encuentras una fuente, anota la duda en pending y deja fuera ese hallazgo. "
        "Los comandos declarados "
        "deben figurar como no ejecutados. No leas ni incluyas secretos o configuración privada. "
        "Indica como pendientes las áreas que no puedas confirmar, sin completar huecos por intuición. "
        "Devuelve solo JSON, sin bloque Markdown. Esquema: "
        + json.dumps(
            {
                "commit": commit,
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


def _normalize_generated_sources(root: Path, report: dict) -> tuple[int, int]:
    """Keep only supported findings in the review and flag gaps for confirmation."""
    adjusted = 0
    unverified = 0
    pending = report.get("pending")
    for key, title in SECTIONS.items():
        entries = report.get(key)
        if not isinstance(entries, list) or len(entries) > 32:
            continue
        grounded = []
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"finding", "sources"}:
                grounded.append(entry)
                continue
            sources = entry["sources"]
            single_source = isinstance(sources, str)
            if single_source:
                sources = [sources] if sources.strip() else []
            if sources is not None and not isinstance(sources, list):
                grounded.append(entry)
                continue
            if not sources:
                finding = _line(entry["finding"], 1400)
                unverified += 1
                if isinstance(pending, list) and len(pending) < _MAX_PENDING:
                    pending.append((f"{title} — Sin fuentes: {finding}")[:700])
                continue
            distinct = list(dict.fromkeys(_source(root, source) for source in sources))
            if single_source or len(distinct) != len(sources) or len(distinct) > _MAX_SOURCES:
                adjusted += 1
                entry = {**entry, "sources": distinct[:_MAX_SOURCES]}
            grounded.append(entry)
        report[key] = grounded
    return adjusted, unverified


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
            if not isinstance(sources, list) or not 1 <= len(sources) <= _MAX_SOURCES:
                raise ValueError(
                    f"Cada hallazgo necesita entre 1 y {_MAX_SOURCES} fuentes: {title}"
                )
            links = ", ".join(f"`{_source(root, path)}`" for path in sources)
            lines.append(f"- {_line(entry['finding'], 1400)}")
            lines.append(f"  Fuentes: {links}")
            found = True
    if not found:
        raise ValueError("El informe debe aportar al menos un hallazgo con fuentes")
    pending = report["pending"]
    if not isinstance(pending, list) or len(pending) > _MAX_PENDING:
        raise ValueError("La lista de datos pendientes no es válida")
    if pending:
        lines.extend(["", "## Pendiente de confirmar", ""])
        lines.extend(f"- {_line(item, 700)}" for item in pending)
    rendered = "\n".join(lines) + "\n"
    if SecretScanner().scan_text(rendered, location=REVIEW_PATH):
        raise ValueError("El informe contiene un posible secreto. Elimínalo antes de importar.")
    return rendered


def _findings_block(bounds: bytes) -> tuple[bytes, bytes, bytes]:
    before, start, rest = bounds.partition(_DETAIL_START)
    if not start and _DETAIL_END not in bounds:
        return bounds, b"", b""
    content, end, after = rest.partition(_DETAIL_END)
    if not end or bounds.count(_DETAIL_START) != 1 or bounds.count(_DETAIL_END) != 1:
        raise ValueError("Los marcadores de hallazgos de Factoría están incompletos o duplicados.")
    return before, start + content + end, after


def preserve_generated_findings(previous: bytes, rendered: bytes) -> bytes:
    """Retain review findings when the regular memory updater renders its own sections."""
    _, block, _ = _findings_block(previous)
    return rendered.rstrip(b"\n") + b"\n\n" + block + b"\n" if block else rendered


def _memory_document(previous: bytes, title: str, keys: tuple[str, ...], report: dict) -> bytes:
    before, existing, after = _findings_block(previous)
    entries = [
        _DETAIL_START.decode(),
        "## Hallazgos de la revisión",
        "",
        f"Commit analizado: `{report['commit']}`",
    ]
    for key in keys:
        entries.extend(("", f"### {SECTIONS[key]}", ""))
        findings = report[key]
        if not findings:
            entries.append(
                "Pendiente de confirmar. La revisión no aporta fuentes para esta sección."
            )
        for finding in findings:
            sources = ", ".join(f"`{source.strip()}`" for source in finding["sources"])
            entries.extend((f"* {finding['finding'].strip()}", f"  Fuentes: {sources}"))
    entries.extend(("", _DETAIL_END.decode()))
    block = "\n".join(entries).encode("utf-8")
    if existing:
        return before + block + after
    if not before.strip():
        before = f"# {title}\n".encode("utf-8")
    separator = b"\n" if before.endswith(b"\n") else b"\n\n"
    return before + separator + block + b"\n"


def _write_documents(writes: dict[Path, bytes], originals: dict[Path, bytes | None]) -> None:
    completed = []
    try:
        for target, content in writes.items():
            previous = target.read_bytes() if target.exists() else None
            if previous != originals[target]:
                raise ValueError("Un documento cambió durante el guardado. Vuelve a revisar.")
            if content != previous:
                atomic_write_bytes(target, content, create=previous is None)
                completed.append(target)
    except (OSError, ValueError) as error:
        unrecovered = []
        for target in reversed(completed):
            try:
                if not target.exists() or target.read_bytes() != writes[target]:
                    unrecovered.append(target.name)
                    continue
                original = originals[target]
                if original is None:
                    target.unlink()
                else:
                    atomic_write_bytes(target, original)
            except OSError:
                unrecovered.append(target.name)
        if unrecovered:
            raise RuntimeError(
                "Guardado interrumpido. Revisa estos documentos: " + ", ".join(unrecovered)
            ) from error
        raise


def review_memory(
    root: Path,
    raw_report: object,
    *,
    confirmed: bool = False,
    token: object = None,
    evidence_root: Path | None = None,
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
        adjustments = {}
        if evidence_root is not None and isinstance(report, dict):
            adjusted, unverified = _normalize_generated_sources(evidence_root, report)
            adjustments = {
                "report": json.dumps(report, ensure_ascii=False, separators=(",", ":"))
                if adjusted or unverified
                else raw_report,
                "findings_without_sources": unverified,
                "findings_with_adjusted_sources": adjusted,
            }
        markdown = _render(evidence_root or root, report, commit)
        target = project_path(root, REVIEW_PATH)
        previous = target.read_bytes() if target.exists() else None
        if previous and not previous.startswith((_MARKER + "\n").encode()):
            raise ValueError(f"Ya existe un documento propio en {REVIEW_PATH}")
        writes = {target: markdown.encode("utf-8")}
        originals = {target: previous}
        tracked = tracked_project_files(root, _DETAILS)
        for name, (title, keys) in _DETAILS.items():
            if name in tracked:
                continue
            document = project_path(root, name)
            original = document.read_bytes() if document.exists() else None
            originals[document] = original
            writes[document] = _memory_document(original or b"", title, keys, report)
        digest = hashlib.sha256(str(root).encode("utf-8"))
        for document, content in writes.items():
            digest.update(str(document.relative_to(root)).encode() + b"\0")
            original = originals[document]
            digest.update(b"\0" if original is None else b"\1" + hashlib.sha256(original).digest())
            digest.update(hashlib.sha256(content).digest())
        revision = digest.hexdigest()
        documents = [document.relative_to(root).as_posix() for document in writes]
        if confirmed:
            if token != revision:
                raise ValueError("La propuesta cambió. Vuelve a revisarla antes de guardarla.")
            ensure_local_project_files(root, documents)
            _write_documents(writes, originals)
    return {
        "path": REVIEW_PATH,
        "markdown": markdown,
        "revision": revision,
        "documents": documents,
        "tracked_documents": sorted(tracked),
        **adjustments,
    }
