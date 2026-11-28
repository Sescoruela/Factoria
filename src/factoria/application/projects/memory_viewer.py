"""Read the selected project's memory documents for the local viewer."""

from pathlib import Path

from factoria.application.governance import ExecutionGovernor, GovernedAction
from factoria.application.policy_runtime import build_execution_context
from factoria.project_paths import project_path

_DOCUMENTS = {
    "AGENTS.md": "Memoria general",
    "docs/memoria/arquitectura.md": "Arquitectura",
    "docs/memoria/flujos.md": "Flujos",
    "docs/memoria/decisiones.md": "Decisiones",
    "docs/memoria/testing.md": "Verificación y pruebas",
    "docs/memoria/revision.md": "Revisión de memoria",
}
_FILE_LIMIT = 256 * 1024
_TOTAL_LIMIT = 1024 * 1024


def read_memory_documents(root: Path) -> dict:
    ExecutionGovernor().assert_allowed(GovernedAction.READ, build_execution_context(root))
    documents = []
    skipped = []
    remaining = _TOTAL_LIMIT
    for relative, title in _DOCUMENTS.items():
        try:
            path = project_path(root, relative)
            if not path.is_file():
                continue
            limit = min(_FILE_LIMIT, remaining)
            with path.open("rb") as stream:
                content = stream.read(limit + 1)
            if len(content) > limit:
                skipped.append(relative)
                continue
            markdown = content.decode("utf-8-sig")
        except (OSError, ValueError):
            skipped.append(relative)
            continue
        remaining -= len(content)
        documents.append({"path": relative, "title": title, "markdown": markdown})
    return {"documents": documents, "skipped": skipped}
