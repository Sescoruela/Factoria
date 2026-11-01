from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from factoria.plugins.registry import PluginRegistry, PluginSource, PluginState


class PluginRegistryTests(unittest.TestCase):
    def _write_plugin(
        self,
        root: Path,
        folder: str,
        *,
        name: str,
        version: str = "0.1.0",
        compatibility: str = ">=0.1.0",
        entrypoint: bool = False,
        deprecated_layout: bool = False,
    ) -> Path:
        plugin_dir = root / folder
        plugin_dir.mkdir(parents=True)
        if deprecated_layout:
            plugin_section = (
                f'name = "{name}"\nversion = "{version}"\ntype = "check"\n'
                'description = "Example plugin"\ncapabilities = ["example"]\n'
            )
        else:
            plugin_section = (
                '[plugin]\n'
                f'name = "{name}"\nversion = "{version}"\ntype = "check"\n'
                'description = "Example plugin"\ncapabilities = ["example"]\n'
            )
        if entrypoint:
            plugin_section += 'entrypoint = "plugin.py"\n'
            (plugin_dir / "plugin.py").write_text("VALUE = 42\n", encoding="utf-8")
        content = plugin_section + f'\n[compatibility]\nfactoria = "{compatibility}"\n'
        (plugin_dir / "plugin.toml").write_text(content, encoding="utf-8")
        return plugin_dir

    def test_higher_priority_plugin_overrides_lower_priority_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            builtin = root / "builtin"
            personal = root / "personal"
            builtin.mkdir()
            personal.mkdir()
            low = self._write_plugin(builtin, "sample", name="sample")
            high = self._write_plugin(personal, "sample", name="sample", version="0.2.0")

            registry = PluginRegistry()
            plugins = registry.discover(
                [
                    (PluginSource.BUILTIN, builtin),
                    (PluginSource.PERSONAL, personal),
                ]
            )

            self.assertEqual(len(plugins), 1)
            self.assertEqual(plugins[0].source, PluginSource.PERSONAL)
            self.assertEqual(plugins[0].path, high)
            self.assertEqual(registry.shadowed[0].shadowed.path, low)

    def test_same_priority_conflict_blocks_registration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            personal = root / "personal"
            personal.mkdir()
            self._write_plugin(personal, "first", name="duplicate")
            self._write_plugin(personal, "second", name="duplicate")

            registry = PluginRegistry()
            plugins = registry.discover([(PluginSource.PERSONAL, personal)])

            self.assertEqual(plugins, ())
            self.assertEqual(len(registry.problems), 2)
            self.assertTrue(
                all(item.state is PluginState.ERROR for item in registry.problems)
            )

    def test_invalid_manifest_is_reported_as_problem_not_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plugins_root = root / "plugins"
            plugins_root.mkdir()
            broken = plugins_root / "broken"
            broken.mkdir()
            (broken / "plugin.toml").write_text(
                '[plugin]\nname = "broken"\nversion = "bad"\n',
                encoding="utf-8",
            )

            registry = PluginRegistry()
            plugins = registry.discover([(PluginSource.PERSONAL, plugins_root)])

            self.assertEqual(plugins, ())
            self.assertEqual(registry.problems[0].state, PluginState.ERROR)

    def test_deprecated_manifest_layout_loads_with_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_plugin(root, "legacy", name="legacy", deprecated_layout=True)

            plugins = PluginRegistry().discover([(PluginSource.PERSONAL, root)])

            self.assertEqual(plugins[0].state, PluginState.WARNING)

    def test_incompatible_plugin_is_not_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_plugin(root, "future", name="future", compatibility=">=9.0.0")

            registry = PluginRegistry(factoria_version="0.1.0")
            plugins = registry.discover([(PluginSource.PERSONAL, root)])

            self.assertEqual(plugins, ())
            self.assertEqual(len(registry.problems), 1)


if __name__ == "__main__":
    unittest.main()
