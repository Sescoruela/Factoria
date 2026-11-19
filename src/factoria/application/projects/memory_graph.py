"""Access the local project memory index under the project's permissions."""

from pathlib import Path
import subprocess

from factoria.application.governance import ExecutionGovernor, GovernedAction
from factoria.application.policy_runtime import build_execution_context
from factoria.memory.graph import build_memory_graph, read_memory_graph
from factoria.project_paths import project_path


def project_memory_graph(
    root: Path,
    *,
    rebuild: bool = False,
    query: str | None = None,
    limit: int = 8,
    read_only: bool = False,
) -> dict:
    context = build_execution_context(root)
    governor = ExecutionGovernor()
    governor.assert_allowed(GovernedAction.READ, context)
    git_dir = Path(
        subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--absolute-git-dir"],
            text=True,
            encoding="utf-8",
        ).strip()
    ).resolve()
    relative = "factoria/memory-graph.sqlite3"
    database = project_path(git_dir, relative)
    for suffix in ("-journal", "-wal", "-shm"):
        project_path(git_dir, relative + suffix)
    if rebuild:
        if read_only:
            raise PermissionError("Modo solo lectura: generación del grafo bloqueada")
        governor.assert_allowed(GovernedAction.WRITE, context)
        return build_memory_graph(root, database)
    return read_memory_graph(database, query=query, limit=limit)
