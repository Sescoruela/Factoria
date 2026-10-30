from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from factoria.plugins.registry import PluginConflictError, PluginRegistry, PluginSource, PluginState


class PluginRegistryTests(unittest.TestCase):
    def _write_plugin(self, root: Path, folder: str, *, name: str, valid: bool = True) -> None:
        plugin_dir = root / folder
        plugin_dir.mkdir(parents=True)
        content = (
            f'name = "{name}"\nversion = "0.1.0"\ntype = "check"\n'
            'description = "Example plugin"\ncapabilities = ["example"]\n'
            if valid
            else 'name = "broken"\n'
        )
        (plugin_dir / "plugin.toml").write_text(content, encoding="utf-8")

    def test_higher_priority_plugin_overrides_lower_priority_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            builtin = root / "builtin"
            personal = root / "personal"
            self._write_plugin(builtin, "sample", name="sample")
            self._write_plugin(personal, "sample", name="sample")

            registry = PluginRegistry()
            plugins = registry.discover(
                [
                    (PluginSource.BUILTIN, builtin),
                    (PluginSource.PERSONAL, personal),
                ]
            )

            self.assertEqual(len(plugins), 1)
            self.assertEqual(plugins[0].source, PluginSource.PERSONAL)

    def test_same_priority_conflict_blocks_registration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            personal = root / "personal"
            self._write_plugin(personal, "first", name="duplicate")
            self._write_plugin(personal, "second", name="duplicate")

            with self.assertRaises(PluginConflictError):
                PluginRegistry().discover([(PluginSource.PERSONAL, personal)])

    def test_invalid_manifest_is_reported_as_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plugins_root = root / "plugins"
            self._write_plugin(plugins_root, "broken", name="broken", valid=False)

            plugins = PluginRegistry().discover([(PluginSource.PERSONAL, plugins_root)])

            self.assertEqual(plugins[0].state, PluginState.ERROR)


if __name__ == "__main__":
    unittest.main()
