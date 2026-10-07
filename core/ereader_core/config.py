"""Strict, atomic user configuration persistence."""
from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_CONFIG = {"theme": "light", "font_size": 20, "wifi_pinned": False}


def validate_config(value: dict) -> dict:
    if set(value) - set(DEFAULT_CONFIG):
        raise ValueError("unknown configuration key")
    merged = DEFAULT_CONFIG | value
    if merged["theme"] not in {"light", "dark"}:
        raise ValueError("theme must be light or dark")
    if not isinstance(merged["font_size"], int) or not 10 <= merged["font_size"] <= 72:
        raise ValueError("font_size must be an integer from 10 to 72")
    if not isinstance(merged["wifi_pinned"], bool):
        raise ValueError("wifi_pinned must be boolean")
    return merged


class ConfigStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict:
        if not self.path.exists():
            return dict(DEFAULT_CONFIG)
        return validate_config(json.loads(self.path.read_text(encoding="utf-8")))

    def save(self, value: dict) -> None:
        validated = validate_config(value)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(validated, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, self.path)
