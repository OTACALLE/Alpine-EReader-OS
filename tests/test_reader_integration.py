import tempfile
import unittest
from pathlib import Path

from reader_integration.launcher import KOReaderLauncher


class ReaderIntegrationTests(unittest.TestCase):
    def test_command_is_a_separate_process_invocation(self):
        with tempfile.TemporaryDirectory() as temporary:
            book = Path(temporary) / "book.epub"
            book.write_text("test")
            command = KOReaderLauncher("/opt/koreader/koreader").command(book)
            self.assertEqual(command, ["/opt/koreader/koreader", str(book)])

    def test_missing_reader_is_not_faked(self):
        with tempfile.TemporaryDirectory() as temporary:
            book = Path(temporary) / "book.epub"
            book.write_text("test")
            self.assertEqual(KOReaderLauncher(Path(temporary) / "missing").launch(book), 127)

    def test_missing_book_raises(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(FileNotFoundError):
                KOReaderLauncher("/x").command(Path(temporary) / "nope.epub")

    def test_launch_runs_reader_and_returns_its_exit_code(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as temporary:
            book = Path(temporary) / "book.epub"
            book.write_text("test")
            reader = Path(temporary) / "koreader"
            reader.write_text("#!/bin/sh\n")
            with mock.patch("reader_integration.launcher.subprocess.run") as run:
                run.return_value.returncode = 7
                self.assertEqual(KOReaderLauncher(reader).launch(book), 7)
            run.assert_called_once_with([str(reader), str(book)], check=False)
