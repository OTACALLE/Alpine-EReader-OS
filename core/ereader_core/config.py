"""Strict, atomic and durable user configuration persistence."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

DEFAULT_CONFIG = {"theme": "light", "font_size": 20, "wifi_pinned": False}


def validate_config(value: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError("configuration must be a JSON object")
    if set(value) - set(DEFAULT_CONFIG):
        raise ValueError("unknown configuration key")
    merged = DEFAULT_CONFIG | value
    if merged["theme"] not in {"light", "dark"}:
        raise ValueError("theme must be light or dark")
    if type(merged["font_size"]) is not int or not 10 <= merged["font_size"] <= 72:
        raise ValueError("font_size must be an integer from 10 to 72")
    if not isinstance(merged["wifi_pinned"], bool):
        raise ValueError("wifi_pinned must be boolean")
    return merged


class ConfigStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        #: Set when the last load() had to discard an unusable file.
        self.last_error: str | None = None
        #: Where the unusable file was preserved, if load() moved one aside.
        self.preserved_path: Path | None = None

    def load(self) -> dict:
        """Return the stored configuration, or defaults if absent or unusable.

        An unreadable/invalid file is never deleted: it is renamed to
        ``<name>.corrupt`` (``.corrupt.1``, ...) so it can be inspected.
        """
        self.last_error = None
        self.preserved_path = None
        if not self.path.exists():
            return dict(DEFAULT_CONFIG)
        try:
            return validate_config(json.loads(self.path.read_text(encoding="utf-8")))
        except (ValueError, UnicodeDecodeError) as error:  # JSONDecodeError is a ValueError
            self.last_error = f"{type(error).__name__}: {error}"
            self.preserved_path = self._preserve_bad_file()
            return dict(DEFAULT_CONFIG)

    def _preserve_bad_file(self) -> Path:
        candidate = self.path.with_name(self.path.name + ".corrupt")
        index = 0
        while candidate.exists():
            index += 1
            candidate = self.path.with_name(f"{self.path.name}.corrupt.{index}")
        os.replace(self.path, candidate)
        return candidate

    def save(self, value: dict) -> None:
        validated = validate_config(value)
        parent = self.path.parent
        parent.mkdir(parents=True, exist_ok=True)
        payload = (json.dumps(validated, sort_keys=True) + "\n").encode("utf-8")
        descriptor, temporary = tempfile.mkstemp(dir=parent, prefix=self.path.name + ".", suffix=".tmp")
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        except BaseException:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise
        self._fsync_directory(parent)

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        # Durability of the rename on POSIX; directories cannot be opened on Windows.
        if os.name != "posix":
            return
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
