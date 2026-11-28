import tempfile
import unittest
from pathlib import Path

from factoria.application.projects.memory_viewer import read_memory_documents


class MemoryViewerTests(unittest.TestCase):
    def test_reads_current_memory_without_an_index_or_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            testing = root / "docs/memoria/testing.md"
            testing.parent.mkdir(parents=True)
            testing.write_text("# Verificación\n\n- Ejecutar pruebas", encoding="utf-8")
            (root / "README.md").write_text("# Fuera de la memoria", encoding="utf-8")
            before = list(root.rglob("*"))
            result = read_memory_documents(root)
            self.assertEqual(result["skipped"], [])
            self.assertEqual(result["documents"], [{
                "path": "docs/memoria/testing.md",
                "title": "Verificación y pruebas",
                "markdown": "# Verificación\n\n- Ejecutar pruebas",
            }])
            self.assertEqual(list(root.rglob("*")), before)
            testing.write_text("# Cambio", encoding="utf-8")
            self.assertEqual(read_memory_documents(root)["documents"][0]["markdown"], "# Cambio")

    def test_skips_symlinks_and_keeps_other_documents(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            memory = root / "docs/memoria"
            memory.mkdir(parents=True)
            (root / "AGENTS.md").write_text("# Memoria", encoding="utf-8")
            target = root / "private.md"
            target.write_text("Fuera del visor", encoding="utf-8")
            try:
                (memory / "revision.md").symlink_to(target)
            except OSError:
                self.skipTest("Este sistema no permite crear enlaces simbólicos")
            result = read_memory_documents(root)
            self.assertEqual(result["skipped"], ["docs/memoria/revision.md"])
            self.assertEqual([doc["path"] for doc in result["documents"]], ["AGENTS.md"])
