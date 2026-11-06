from contextlib import redirect_stderr
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from factoria.entrypoint import main
from tools.release_artifacts import check_version, verify_checksums, write_checksums


class ReleaseArtifactsTests(unittest.TestCase):
    def test_real_metadata_matches(self):
        self.assertEqual(check_version(Path(__file__).resolve().parents[1]), "0.3.0")

    def test_metadata_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "src/factoria").mkdir(parents=True)
            (root / "pyproject.toml").write_text('[project]\nversion="0.3.0"')
            (root / "src/factoria/release.toml").write_text('version="0.2.0"')
            with self.assertRaises(ValueError):
                check_version(root)

    def test_manifest_detects_corruption_and_missing_assets(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            asset = root / "Factoria.exe"
            asset.write_bytes(b"fixture binary")
            write_checksums(root, [asset.name])
            self.assertEqual(verify_checksums(root), [asset.name])
            asset.write_bytes(b"modified binary")
            with self.assertRaisesRegex(ValueError, "mismatch"):
                verify_checksums(root)
            asset.unlink()
            with self.assertRaises(ValueError):
                verify_checksums(root)

    def test_unsafe_or_duplicate_names_do_not_replace_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = root / "SHA256SUMS"
            manifest.write_text("original")
            for names in [["../secret"], ["C:secret"], ["a\\b"], ["a", "a"], ["SHA256SUMS"], []]:
                with self.subTest(names=names), self.assertRaises(ValueError):
                    write_checksums(root, names)
                self.assertEqual(manifest.read_text(), "original")

    def test_malformed_duplicate_and_traversal_manifests_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "a.exe").write_bytes(b"a")
            manifest = write_checksums(root, ["a.exe"])
            line = manifest.read_text()
            for content in ["", "not a hash", line + line, "0" * 64 + "  ../outside\n"]:
                manifest.write_text(content)
                with self.subTest(content=content), self.assertRaises(ValueError):
                    verify_checksums(root)

    def test_frozen_update_and_rollback_never_construct_python_updater(self):
        for command in [["update", "--yes"], ["rollback", "--yes"]]:
            with patch("sys.frozen", True, create=True), patch("factoria.entrypoint.UpdateService") as service:
                output = io.StringIO()
                with redirect_stderr(output):
                    self.assertEqual(main(command), 1)
                service.assert_not_called()
                self.assertIn("No usa pip", output.getvalue())
