from __future__ import annotations

import os
from pathlib import Path
import subprocess


class KOReaderLauncher:
    def __init__(self, executable: str | Path = "/usr/bin/koreader") -> None:
        # Keep a target command in POSIX form even when host tests run on Windows.
        self.executable = str(executable)

    def command(self, book: Path) -> list[str]:
        if not book.is_file():
            raise FileNotFoundError(book)
        return [self.executable, os.fspath(book)]

    def launch(self, book: Path) -> int:
        command = self.command(book)
        if not Path(self.executable).is_file():
            print(f"KOReader is not installed at {self.executable}; cannot render {book}.")
            return 127
        return subprocess.run(command, check=False).returncode
