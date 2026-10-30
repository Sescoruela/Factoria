from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from factoria.config.loader import ConfigError, load_global_config, load_project_config, resolve_config
from factoria.config.models import RuntimeOverrides
from factoria.domain.permissions import PermissionProfile


class ConfigLoaderTests(unittest.TestCase):
    def test_global_project_and_runtime_configuration_are_merged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            global_path = root / "global.toml"
            project_path = root / "project.toml"
            global_path.write_text(
                'default_profile = "normal"\ndefault_tool = "codex"\nmax_agents = 2\n\n'
                '[plugins]\npersonal_paths = ["plugins/personal"]\n',
                encoding="utf-8",
            )
            project_path.write_text(
                'profile = "safe"\nmax_agents = 3\n\n'
                '[flows]\nallowed = ["fix", "feature"]\nblocked = ["release"]\n',
                encoding="utf-8",
            )

            resolved = resolve_config(
                load_global_config(global_path),
                load_project_config(project_path),
                RuntimeOverrides(profile=PermissionProfile.POWER, max_agents=4),
            )

            self.assertEqual(resolved.profile, PermissionProfile.POWER)
            self.assertEqual(resolved.tool, "codex")
            self.assertEqual(resolved.max_agents, 4)
            self.assertEqual(resolved.allowed_flows, ("fix", "feature"))
            self.assertTrue(resolved.personal_plugin_paths[0].is_absolute())

    def test_flow_cannot_be_both_allowed_and_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "project.toml"
            path.write_text(
                '[flows]\nallowed = ["fix"]\nblocked = ["fix"]\n',
                encoding="utf-8",
            )
            with self.assertRaises(ConfigError):
                load_project_config(path)

    def test_project_cannot_define_default_tool(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "project.toml"
            path.write_text('default_tool = "opencode"\n', encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_project_config(path)


if __name__ == "__main__":
    unittest.main()
