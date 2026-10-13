"""Host-runnable development UI; target rendering backend remains device-port work."""
from __future__ import annotations

import argparse
from pathlib import Path

from core.ereader_core.storage import LibraryStore
from reader_integration.launcher import KOReaderLauncher
from .state import Screen, ShellState


def main() -> int:
    parser = argparse.ArgumentParser(description="Alpine EReader OS development shell")
    parser.add_argument("--data-root", type=Path, default=Path("./ereader-data"))
    parser.add_argument("--open", type=Path, help="launch an existing book through KOReader")
    args = parser.parse_args()
    library = LibraryStore(args.data_root)
    state = ShellState()
    if args.open:
        state.open_book(str(args.open))
        try:
            return KOReaderLauncher().launch(args.open)
        except FileNotFoundError:
            print(f"book not found: {args.open}")
            return 2
    print("Alpine EReader Shell (development backend)")
    for book in library.discover():
        print(book.name)
    print("screen=" + state.screen.value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
