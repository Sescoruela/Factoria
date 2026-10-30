from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from factoria.config.loader import ConfigError, load_project_config
from factoria.domain.models import MemoryDocumentKind, ProjectKind


class MemoryConfigTests(unittest.TestCase):
    def test_project_memory_settings_are_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "project.toml"
            path.write_text(
                '[memory]\ntype = "active"\n\n'
                '[memory.staleness]\narchitecture = 25\nflows = 15\n',
                encoding="utf-8",
            )

            config = load_project_config(path)

            self.assertEqual(config.memory.project_kind, ProjectKind.ACTIVE)
            self.assertEqual(
                config.memory.stale_after_commits[MemoryDocumentKind.ARCHITECTURE],
                25,
            )

    def test_unknown_memory_document_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "project.toml"
            path.write_text(
                '[memory.staleness]\nunknown = 10\n',
                encoding="utf-8",
            )
            with self.assertRaises(ConfigError):
                load_project_config(path)


if __name__ == "__main__":
    unittest.main()
