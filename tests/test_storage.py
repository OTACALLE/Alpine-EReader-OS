import tempfile
import unittest
from pathlib import Path

from core.ereader_core.storage import LibraryStore


class StorageTests(unittest.TestCase):
    def test_discovers_only_supported_books_in_sorted_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = LibraryStore(Path(temporary))
            store.initialize()
            (store.books / "z.pdf").write_text("x")
            (store.books / "A.epub").write_text("x")
            (store.books / "ignore.exe").write_text("x")
            self.assertEqual([book.name for book in store.discover()], ["A.epub", "z.pdf"])
