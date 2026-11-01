from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from factoria.plugins import PluginRuntime
from factoria.plugins.registry import PluginRegistry, PluginSource, PluginState


_MANIFEST = """[plugin]\nname = {name!r}\nversion = \"1.0.0\"\ntype = \"check\"\ndescription = \"demo plugin\"\n{entrypoint}\n\n[compatibility]\nfactoria = \">=0.1.0\"\n"""


def write_plugin(root: Path, folder: str, *, name: str, executable: bool = False) -> Path:
    plugin = root / folder
    plugin.mkdir(parents=True)
    entry = 'entrypoint = "plugin.py"' if executable else ""
    (plugin / "plugin.toml").write_text(
        _MANIFEST.format(name=name, entrypoint=entry), encoding="utf-8"
    )
    if executable:
        (plugin / "plugin.py").write_text(
            "def load_plugin():\n    return {'loaded': True}\n", encoding="utf-8"
        )
    return plugin


class PluginRegistryTests(unittest.TestCase):
    def test_higher_priority_plugin_shadows_lower_priority(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            builtin = root / "builtin"
            personal = root / "personal"
            write_plugin(builtin, "demo", name="demo")
            write_plugin(personal, "demo", name="demo")

            registry = PluginRegistry(factoria_version="0.2.0")
            registry.discover(
                [
                    (PluginSource.BUILTIN, builtin),
                    (PluginSource.PERSONAL, personal),
                ]
            )

            self.assertEqual(len(registry.plugins), 1)
            self.assertEqual(registry.plugins[0].source, PluginSource.PERSONAL)
            self.assertEqual(len(registry.shadowed), 1)
            self.assertEqual(registry.shadowed[0].shadowed.source, PluginSource.BUILTIN)

    def test_same_priority_collision_blocks_both_definitions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first"
            second = root / "second"
            write_plugin(first, "demo-a", name="demo")
            write_plugin(second, "demo-b", name="demo")

            registry = PluginRegistry(factoria_version="0.2.0")
            registry.discover(
                [
                    (PluginSource.PERSONAL, first),
                    (PluginSource.PERSONAL, second),
                ]
            )

            self.assertEqual(registry.plugins, ())
            self.assertEqual(len(registry.problems), 2)
            self.assertTrue(all(item.state is PluginState.ERROR for item in registry.problems))
            self.assertTrue(all("neither definition will load" in item.warnings[-1] for item in registry.problems))

    def test_higher_priority_plugin_can_resolve_lower_priority_collision(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            org_a = root / "org-a"
            org_b = root / "org-b"
            personal = root / "personal"
            write_plugin(org_a, "demo-a", name="demo")
            write_plugin(org_b, "demo-b", name="demo")
            write_plugin(personal, "demo", name="demo")

            registry = PluginRegistry(factoria_version="0.2.0")
            registry.discover(
                [
                    (PluginSource.ORGANIZATION, org_a),
                    (PluginSource.ORGANIZATION, org_b),
                    (PluginSource.PERSONAL, personal),
                ]
            )

            self.assertEqual(len(registry.plugins), 1)
            self.assertEqual(registry.plugins[0].source, PluginSource.PERSONAL)

    def test_entrypoint_cannot_escape_plugin_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "plugins"
            plugin = source / "demo"
            plugin.mkdir(parents=True)
            (root / "outside.py").write_text("x = 1\n", encoding="utf-8")
            (plugin / "plugin.toml").write_text(
                """[plugin]\nname = \"demo\"\nversion = \"1.0.0\"\ntype = \"check\"\ndescription = \"demo\"\nentrypoint = \"../../outside.py\"\n""",
                encoding="utf-8",
            )

            registry = PluginRegistry(factoria_version="0.2.0")
            registry.discover([(PluginSource.PERSONAL, source)])

            self.assertEqual(registry.plugins, ())
            self.assertEqual(len(registry.problems), 1)
            self.assertIn("must stay inside", registry.problems[0].warnings[0])


class PluginRuntimeTests(unittest.TestCase):
    def test_external_executable_plugin_loads_and_is_visible_as_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "plugins"
            write_plugin(source, "demo", name="demo", executable=True)
            runtime = PluginRuntime(factoria_version="0.2.0")

            with patch.object(PluginRuntime, "configured_roots", return_value=[]):
                report = runtime.discover_and_load(
                    extra_roots=[(PluginSource.PERSONAL, source)]
                )

            self.assertEqual(report.problems, ())
            self.assertEqual(len(report.loaded), 1)
            loaded = report.loaded[0]
            self.assertEqual(loaded.instance, {"loaded": True})
            self.assertEqual(loaded.record.state, PluginState.WARNING)
            self.assertTrue(any("trusted Python code" in item for item in loaded.record.warnings))

    def test_entrypoint_without_factory_is_reported_as_error_and_not_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "plugins"
            plugin = write_plugin(source, "demo", name="demo", executable=True)
            (plugin / "plugin.py").write_text("VALUE = 1\n", encoding="utf-8")
            runtime = PluginRuntime(factoria_version="0.2.0")

            with patch.object(PluginRuntime, "configured_roots", return_value=[]):
                report = runtime.discover_and_load(
                    extra_roots=[(PluginSource.PERSONAL, source)]
                )

            self.assertEqual(report.loaded, ())
            self.assertEqual(len(report.problems), 1)
            self.assertIn("load_plugin()", report.problems[0].warnings[-1])


if __name__ == "__main__":
    unittest.main()
