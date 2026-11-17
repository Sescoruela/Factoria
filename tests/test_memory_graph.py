import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from factoria.commands.project import run_project_cli


class MemoryGraphTests(unittest.TestCase):
    def setUp(self):
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.root = Path(workspace.name).resolve() / "repo"
        self.root.mkdir()
        self.docs = self.root / "docs/memoria"
        self.docs.mkdir(parents=True)
        home = patch("pathlib.Path.home", return_value=self.root.parent / "home")
        home.start()
        self.addCleanup(home.stop)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / "src").mkdir()
        self.memory = self.root / "AGENTS.md"
        self.memory.write_text(
            "# Proyecto\n\n## Módulos\n- **API**: `src/`\n"
            "\n## Dependencias\n- **API** → SQL\n"
            "\n<!-- factoria:integration:start -->\n## Generado\nruido\n"
            "<!-- factoria:integration:end -->\n",
            encoding="utf-8",
        )
        (self.docs / "decisiones.md").write_text(
            "# Decisiones\n\n## Paginación\nUsar cursor en la API. [Memoria](../../AGENTS.md)\n",
            encoding="utf-8",
        )

    def cli(self, *args, read_only=False, ok=True):
        flags = ["--read-only"] if read_only else []
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = run_project_cli(
                ["--project", str(self.docs), *flags, "project", "memory-graph", *args]
            )
        self.assertEqual(code, 0 if ok else 1, stderr.getvalue())
        return stdout.getvalue() if ok else stderr.getvalue()

    def test_builds_and_recalls_explicit_relations_without_worktree_changes(self):
        status = ["git", "-C", str(self.root), "status", "--porcelain"]
        before = subprocess.check_output(status)
        result = json.loads(self.cli("build"))
        self.assertGreater(result["edges"], 0)
        self.assertEqual(subprocess.check_output(status), before)
        graph = json.loads(self.cli("export", read_only=True))
        labels = {node["id"]: node["label"] for node in graph["nodes"]}
        self.assertNotIn("Generado", labels.values())
        edges = {
            (labels[edge["origin"]], edge["relation"], labels[edge["target"]])
            for edge in graph["edges"]
        }
        self.assertIn(("API", "depends_on", "SQL"), edges)
        self.assertIn(("API", "has_path", "src"), edges)
        self.assertIn(("Paginación", "references", "AGENTS.md"), edges)
        recall = json.loads(self.cli("recall", "paginacion", "--limit", "1", read_only=True))
        self.assertEqual(recall["matches"][0]["source"], "docs/memoria/decisiones.md")
        self.assertEqual(recall["matches"][0]["line"], 3)
        self.assertEqual(len(recall["matches"]), 1)
        self.assertIn("depends_on", self.cli("export", "--format", "mermaid"))

    def test_rebuild_replaces_old_entries_and_rejected_source_preserves_index(self):
        self.cli("build")
        before = self.cli("export")
        (self.docs / "secret.md").write_text('password = "synthetic-test-only"\n', encoding="utf-8")
        self.assertIn("Posible secreto", self.cli("build", ok=False))
        self.assertEqual(self.cli("export"), before)
        (self.docs / "secret.md").unlink()
        (self.docs / "decisiones.md").unlink()
        self.cli("build")
        self.assertEqual(json.loads(self.cli("recall", "paginacion"))["matches"], [])

    def test_read_only_and_missing_index_never_create_database(self):
        self.assertIn("Grafo sin generar", self.cli("recall", "API", read_only=True, ok=False))
        self.assertIn("solo lectura", self.cli("build", read_only=True, ok=False))
        self.assertFalse((self.root / ".git/factoria").exists())
