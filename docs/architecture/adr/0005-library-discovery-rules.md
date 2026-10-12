# ADR 0005: Library discovery rules

Status: accepted for the host reference implementation.

`LibraryStore.discover()` scans `Books/` **recursively** (up to 4 levels) because
users copy whole author/series folders over MTP. It skips symlinks (files and
folders, so a link cannot expose files outside `Books/`), hidden entries
(including macOS `._*` files), zero-byte files and partial copies, and only
accepts `.epub`, `.pdf` and `.txt`. Results are ordered by case-folded relative
path. Covers, metadata, hashing and `inotify` rescans (ARCHITECTURE.md §16-17)
are not implemented yet.
