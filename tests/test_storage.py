import os
import tempfile
import unittest
from pathlib import Path

from core.ereader_core.storage import MAX_DEPTH, LibraryStore


def _write(path: Path, data: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data)
    return path


class StorageTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = LibraryStore(Path(self._tmp.name))
        self.store.initialize()

    def names(self):
        return [p.relative_to(self.store.books).as_posix() for p in self.store.discover()]

    def test_discovers_only_supported_books_in_sorted_order(self):
        _write(self.store.books / "z.pdf")
        _write(self.store.books / "A.epub")
        _write(self.store.books / "ignore.exe")
        self.assertEqual([book.name for book in self.store.discover()], ["A.epub", "z.pdf"])

    def test_suffix_match_is_case_insensitive(self):
        _write(self.store.books / "Loud.EPUB")
        self.assertEqual(self.names(), ["Loud.EPUB"])

    def test_recurses_into_subfolders_sorted_by_relative_path(self):
        _write(self.store.books / "b.txt")
        _write(self.store.books / "Author" / "Series" / "one.epub")
        _write(self.store.books / "Author" / "two.pdf")
        self.assertEqual(self.names(), ["Author/Series/one.epub", "Author/two.pdf", "b.txt"])

    def test_depth_limit(self):
        deep = self.store.books.joinpath(*[f"d{i}" for i in range(MAX_DEPTH)]) / "ok.epub"
        too_deep = self.store.books.joinpath(*[f"d{i}" for i in range(MAX_DEPTH + 1)]) / "no.epub"
        _write(deep)
        _write(too_deep)
        self.assertEqual([Path(n).name for n in self.names()], ["ok.epub"])

    def test_skips_zero_byte_hidden_and_partial_files(self):
        _write(self.store.books / "empty.epub", "")
        _write(self.store.books / "._mac.epub")
        _write(self.store.books / ".hidden" / "secret.epub")
        _write(self.store.books / "book.epub.part")
        _write(self.store.books / "real.epub")
        self.assertEqual(self.names(), ["real.epub"])

    def test_skips_symlinked_files_and_folders(self):
        outside = Path(self._tmp.name) / "outside"
        _write(outside / "stolen.epub")
        secret = _write(outside / "secret.txt")
        try:
            os.symlink(secret, self.store.books / "evil.txt")
            os.symlink(outside, self.store.books / "linked-dir", target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable on this host")
        _write(self.store.books / "real.epub")
        self.assertEqual(self.names(), ["real.epub"])

    def test_discover_creates_the_layout(self):
        fresh = LibraryStore(Path(self._tmp.name) / "fresh")
        self.assertEqual(fresh.discover(), [])
        for folder in (fresh.books, fresh.documents, fresh.notes, fresh.dictionary, fresh.config):
            self.assertTrue(folder.is_dir())


if __name__ == "__main__":
    unittest.main()
