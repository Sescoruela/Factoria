from __future__ import annotations

import unittest
from importlib.metadata import version

from factoria import cli
from factoria.entrypoint import installed_version
from factoria.package_version import installed_semver, installed_version_text


class PackageVersionTests(unittest.TestCase):
    def test_package_metadata_is_the_single_runtime_version_source(self) -> None:
        expected = version("factoria")
        self.assertEqual(installed_version_text(), expected)
        self.assertEqual(str(installed_semver()), expected)
        self.assertEqual(str(installed_version()), expected)
        self.assertEqual(cli.FACTORIA_VERSION, expected)

    def test_legacy_cli_version_is_not_hardcoded(self) -> None:
        self.assertNotEqual(cli.FACTORIA_VERSION, "0.1.0")


if __name__ == "__main__":
    unittest.main()
