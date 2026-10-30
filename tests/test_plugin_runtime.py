from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from factoria.plugins import PluginRegistry, PluginSource, load_plugin


class PluginRuntimeTests(unittest.TestCase):
    def test_valid_entrypoint_can_be_loaded_after_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plugin = root / "example"
            plugin.mkdir()
            (plugin / "plugin.toml").write_text(
                """
[plugin]
name = "example"
version = "0.1.0"
type = "check"
description = "Executable plugin"
entrypoint = "plugin.py"

[compatibility]
factoria = ">=0.1.0"
""".strip(),
                encoding="utf-8",
            )
            (plugin / "plugin.py").write_text("VALUE = 42\n", encoding="utf-8")

            records = PluginRegistry().discover([(PluginSource.PERSONAL, root)])
            loaded = load_plugin(records[0])

            self.assertIsNotNone(loaded.module)
            assert loaded.module is not None
            self.assertEqual(loaded.module.VALUE, 42)


if __name__ == "__main__":
    unittest.main()
