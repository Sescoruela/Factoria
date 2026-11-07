"""Persistence contracts used by every resource editor, not implementation snapshots."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from factoria.storage import atomic_write_bytes, staged_bytes


class AtomicStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.target = self.directory / "resource.md"
        self.target.write_bytes(b"original")

    def assert_original_without_temporary_files(self):
        self.assertEqual(self.target.read_bytes(), b"original")
        self.assertEqual(list(self.directory.iterdir()), [self.target])

    def test_replace_and_create_preserve_exact_utf8_and_trailing_whitespace(self):
        content = "# Revisión\r\n\r\n- Regla.  \r\n".encode("utf-8")
        atomic_write_bytes(self.target, content)
        self.assertEqual(self.target.read_bytes(), content)
        target = self.directory / "nested" / "new.md"
        atomic_write_bytes(target, content, create=True)
        self.assertEqual(target.read_bytes(), content)

    def test_exclusive_create_preserves_a_competing_file(self):
        with self.assertRaises(FileExistsError):
            atomic_write_bytes(self.target, b"overwrite", create=True)
        self.assert_original_without_temporary_files()

    def test_publication_failure_keeps_old_resource_and_removes_staged_bytes(self):
        with patch("factoria.storage.os.replace", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                atomic_write_bytes(self.target, b"new")
        self.assert_original_without_temporary_files()

    def test_flush_failure_keeps_old_resource_and_cleans_partial_staging(self):
        with patch("factoria.storage.os.fsync", side_effect=OSError("flush failure")):
            with self.assertRaises(OSError):
                atomic_write_bytes(self.target, b"new")
        self.assert_original_without_temporary_files()

    def test_revision_rejection_after_staging_does_not_publish(self):
        with self.assertRaisesRegex(ValueError, "stale revision"):
            with staged_bytes(self.target, b"unpublished") as temporary:
                self.assertEqual(temporary.read_bytes(), b"unpublished")
                self.assertEqual(self.target.read_bytes(), b"original")
                raise ValueError("stale revision")
        self.assert_original_without_temporary_files()
