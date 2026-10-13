"""Host-independent file modes for images.

Windows does not carry POSIX permission bits, so modes are derived from the
path and content, never from the host file system.  This is what makes image
hashes identical on Windows and Linux.
"""
from __future__ import annotations

EXECUTABLE_DIRECTORIES = ("bin/", "sbin/", "usr/bin/", "usr/sbin/", "usr/libexec/", "etc/init.d/")


def file_mode(relative_posix_path: str, data: bytes) -> int:
    """Return 0o755 for executables/scripts, else 0o644 (regular-file bits excluded)."""
    if data.startswith(b"#!") or data.startswith(b"\x7fELF"):
        return 0o755
    if relative_posix_path.startswith(EXECUTABLE_DIRECTORIES):
        return 0o755
    return 0o644
