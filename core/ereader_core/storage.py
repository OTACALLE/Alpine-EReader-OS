"""Persistent user-data layout and safe library discovery."""
from __future__ import annotations

from pathlib import Path

SUPPORTED_BOOK_SUFFIXES = {".epub", ".pdf", ".txt"}


class LibraryStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.books = root / "Books"
        self.documents = root / "Documents"
        self.notes = root / "Notes"
        self.dictionary = root / "Dictionary"
        self.config = root / "Config"

    def initialize(self) -> None:
        for directory in (self.books, self.documents, self.notes, self.dictionary, self.config):
            directory.mkdir(parents=True, exist_ok=True)

    def discover(self) -> list[Path]:
        self.initialize()
        return sorted(
            (entry for entry in self.books.iterdir() if entry.is_file() and entry.suffix.lower() in SUPPORTED_BOOK_SUFFIXES),
            key=lambda entry: entry.name.casefold(),
        )
