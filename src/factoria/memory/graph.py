"""Local, rebuildable graph of explicit relationships in project memory."""

from __future__ import annotations

import hashlib
import posixpath
import re
import sqlite3
import unicodedata
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

from factoria.project_paths import project_path
from factoria.security.secrets import SecretScanner


HEADING = re.compile(r"^ {0,3}#{1,6}\s+(.+?)\s*$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
REFERENCES = re.compile(r"`([^`\n]+)`|\[[^\]\n]*\]\(([^)\s]+)\)")
DEPENDENCY = re.compile(r"^- \*\*(.+?)\*\* → (.+)$")
MODULE = re.compile(r"^- \*\*(.+?)\*\*:\s*(.+)$")
INTEGRATION = re.compile(
    r"<!-- factoria:integration:start -->.*?<!-- factoria:integration:end -->", re.S
)


def _searchable(text: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(char)
    )


def _sections(text: str) -> Iterator[tuple[str, int, str]]:
    title, start, fence = "Introducción", 1, ""
    lines = []
    for number, line in enumerate(text.splitlines(), 1):
        marker = FENCE.match(line)
        if marker:
            sequence, suffix = marker.groups()
            if not fence:
                fence = sequence
            elif sequence.startswith(fence) and not suffix.strip():
                fence = ""
            lines.append(line)
            continue
        match = HEADING.match(line) if not fence else None
        if match:
            if any(item.strip() for item in lines):
                yield title, start, "\n".join(lines).strip()
            title, start, lines = match[1], number, []
        else:
            lines.append(line)
    if any(item.strip() for item in lines):
        yield title, start, "\n".join(lines).strip()


def build_memory_graph(root: Path, database: Path) -> dict:
    scanner = SecretScanner()
    docs = project_path(root, "docs/memoria")
    sources = ["AGENTS.md"] + (
        sorted(path.relative_to(root).as_posix() for path in docs.glob("*.md"))
        if docs.is_dir()
        else []
    )
    nodes = {}
    edges = set()

    def add(
        kind: str,
        label: str,
        source: str | None = None,
        line: int | None = None,
        content: str = "",
    ) -> str:
        key = (kind, label, source or "", str(line or ""))
        node_id = hashlib.sha256("\0".join(key).encode()).hexdigest()[:24]
        nodes[node_id] = (node_id, kind, label, source, line, content)
        return node_id

    def add_path(relative: str) -> str | None:
        try:
            target = project_path(root, relative)
            parts = target.relative_to(root).parts
            if parts and ".git" not in parts and (target.is_file() or target.is_dir()):
                normalized = target.relative_to(root).as_posix()
                return add("path", normalized, normalized)
        except (OSError, ValueError):
            pass
        return None

    for source in sources:
        path = project_path(root, source)
        if not path.is_file():
            continue
        with path.open("rb") as handle:
            data = handle.read(scanner.max_file_bytes + 1)
        if len(data) > scanner.max_file_bytes:
            raise ValueError(f"Archivo de memoria demasiado grande para indexar: {source}")
        text = data.decode("utf-8")
        if scanner.scan_text(text, location=source):
            raise ValueError(f"Posible secreto en la memoria: {source}")
        if source == "AGENTS.md":
            text = INTEGRATION.sub(lambda match: "\n" * match[0].count("\n"), text)
        document = add("document", source, source)
        for title, line, content in _sections(text):
            section = add("section", title, source, line, content)
            edges.add((document, "contains", section))
            if title == "Módulos":
                for entry in content.splitlines():
                    match = MODULE.match(entry)
                    if match:
                        module = add("module", match[1])
                        edges.add((section, "describes", module))
                        for value in match[2].partition(";")[0].split(","):
                            path_id = add_path(value.strip().strip("`"))
                            if path_id:
                                edges.add((module, "has_path", path_id))
            if title == "Dependencias":
                # The memory format records explicit module dependencies with an arrow.
                for entry in content.splitlines():
                    match = DEPENDENCY.match(entry)
                    if match:
                        origin = add("module", match[1])
                        edges.add((section, "describes", origin))
                        for value in match[2].split(","):
                            name = value.strip()
                            if name:
                                edges.add((origin, "depends_on", add("module", name)))
            for match in REFERENCES.finditer(content):
                reference = (match[1] or match[2]).split("#", 1)[0]
                if not reference or "://" in reference:
                    continue
                # Markdown links resolve relative to the document. Code paths use the repo root.
                candidate = (
                    posixpath.normpath((Path(source).parent / reference).as_posix())
                    if match[2]
                    else reference
                )
                path_id = add_path(candidate)
                if path_id:
                    edges.add((section, "references", path_id))

    if not nodes:
        raise ValueError("No hay memoria para indexar. Prepara AGENTS.md o docs/memoria primero.")
    database.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version != 1:
            existing = db.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone()
            if version or existing:
                raise ValueError("Formato de grafo incompatible")
            db.execute(
                "CREATE TABLE nodes (id TEXT PRIMARY KEY, kind TEXT, label TEXT, "
                "source TEXT, line INTEGER, content TEXT, search TEXT)"
            )
            db.execute(
                "CREATE TABLE edges (origin TEXT, relation TEXT, target TEXT, "
                "PRIMARY KEY (origin, relation, target))"
            )
            db.execute("CREATE INDEX edges_target ON edges (target)")
            db.execute("PRAGMA user_version = 1")
        db.execute("DELETE FROM edges")
        db.execute("DELETE FROM nodes")
        db.executemany(
            "INSERT INTO nodes VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                (*node, _searchable(" ".join((node[2], node[3] or "", node[5]))))
                for node in nodes.values()
            ),
        )
        db.executemany("INSERT INTO edges VALUES (?, ?, ?)", sorted(edges))
    return {"nodes": len(nodes), "edges": len(edges)}


def read_memory_graph(database: Path, *, query: str | None = None, limit: int = 8) -> dict:
    if not 1 <= limit <= 30:
        raise ValueError("El límite debe estar entre 1 y 30")
    if query is not None:
        terms = list(dict.fromkeys(re.findall(r"\w+", _searchable(query))))
        if not terms or len(terms) > 12 or len(query) > 300:
            raise ValueError("La consulta requiere entre 1 y 12 términos y hasta 300 caracteres")
    if not database.is_file():
        raise FileNotFoundError("Grafo sin generar. Ejecuta factoria project memory-graph build.")
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute("BEGIN")
        if db.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise ValueError("Formato de grafo incompatible")
        columns = "id, kind, label, source, line"
        if query is None:
            nodes = db.execute(f"SELECT {columns} FROM nodes ORDER BY source, line, label, id")
            edges = db.execute("SELECT * FROM edges ORDER BY origin, relation, target")
            return {"nodes": [dict(row) for row in nodes], "edges": [dict(row) for row in edges]}

        score = " + ".join("(instr(search, ?) > 0)" for _ in terms)
        matches = db.execute(
            f"SELECT {columns}, substr(content, 1, 600) AS excerpt, {score} AS score "
            "FROM nodes WHERE score > 0 ORDER BY score DESC, kind = 'section' DESC, label, id "
            "LIMIT ?",
            (*terms, limit),
        ).fetchall()
        if not matches:
            return {"matches": [], "related": [], "edges": []}
        ids = [item["id"] for item in matches]
        placeholders = ", ".join("?" for _ in ids)
        edges = db.execute(
            f"SELECT * FROM edges WHERE origin IN ({placeholders}) OR target IN ({placeholders}) "
            "ORDER BY origin, relation, target LIMIT ?",
            (*ids, *ids, limit),
        ).fetchall()
        related = sorted({edge[key] for edge in edges for key in ("origin", "target")} - set(ids))
        markers = ", ".join("?" for _ in related)
        nodes = (
            db.execute(
                f"SELECT {columns} FROM nodes WHERE id IN ({markers}) ORDER BY label, id", related
            )
            if related
            else ()
        )
        return {
            "matches": [dict(row) for row in matches],
            "related": [dict(row) for row in nodes],
            "edges": [dict(row) for row in edges],
        }


def graph_mermaid(graph: dict) -> str:
    lines = ["flowchart TD"]
    for node in graph["nodes"]:
        # Keep labels inert in renderers that interpret Markdown or HTML.
        label = re.sub(r"[^\w ./-]", " ", node["label"][:96]).strip() or node["kind"]
        lines.append(f'  n{node["id"]}["{label}"]')
    for edge in graph["edges"]:
        lines.append(f"  n{edge['origin']} -->|{edge['relation']}| n{edge['target']}")
    return "\n".join(lines)
