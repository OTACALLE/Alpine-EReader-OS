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
