import tempfile
import unittest
from pathlib import Path

from factoria.config.loader import ConfigError, load_organization_config, load_project_config


class ExecutionPolicyConfigTests(unittest.TestCase):
    def test_organization_policy_loads_blocked_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "organization.toml"
            path.write_text(
                '[permissions]\nblocked_actions = ["destructive", "command"]\n',
                encoding="utf-8",
            )
            config = load_organization_config(path)
            self.assertEqual(config.blocked_actions, ("destructive", "command"))

    def test_project_policy_loads_blocked_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.toml"
            path.write_text(
                '[permissions]\nblocked_actions = ["destructive"]\n',
                encoding="utf-8",
            )
            config = load_project_config(path)
            self.assertEqual(config.blocked_actions, ("destructive",))

    def test_unknown_action_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "organization.toml"
            path.write_text(
                '[permissions]\nblocked_actions = ["teleport"]\n',
                encoding="utf-8",
            )
            with self.assertRaises(ConfigError):
                load_organization_config(path)


if __name__ == "__main__":
    unittest.main()
