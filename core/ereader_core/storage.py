"""Persistent user-data layout and safe library discovery."""
from __future__ import annotations

import os
from pathlib import Path

SUPPORTED_BOOK_SUFFIXES = {".epub", ".pdf", ".txt"}
#: Deepest sub-folder level scanned under Books/ (Books/ itself is level 0).
MAX_DEPTH = 4


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
        """Return supported books under Books/, recursively (ADR 0005).

        Skipped: symlinks (files and folders), hidden entries, zero-byte files
        (partial copies) and anything deeper than MAX_DEPTH.
        """
        self.initialize()
        found: list[Path] = []
        for current, directories, files in os.walk(self.books, followlinks=False):
            depth = len(Path(current).relative_to(self.books).parts)
            directories[:] = [
                name for name in directories
                if not name.startswith(".") and not (Path(current) / name).is_symlink() and depth < MAX_DEPTH
            ]
            for name in files:
                path = Path(current) / name
                if name.startswith(".") or path.suffix.lower() not in SUPPORTED_BOOK_SUFFIXES:
                    continue
                if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
                    continue
                found.append(path)
        found.sort(key=lambda entry: entry.relative_to(self.books).as_posix().casefold())
        return found
