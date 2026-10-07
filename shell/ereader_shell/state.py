from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Screen(str, Enum):
    LIBRARY = "library"
    READER = "reader"
    CATALOGS = "catalogs"
    SEARCH = "search"
    SETTINGS = "settings"
    NETWORK = "network"
    DEVICE_INFO = "device-info"
    UPDATE = "update"
    RECOVERY = "recovery"


@dataclass
class ShellState:
    """A deliberately small navigation stack; no desktop/app model exists."""
    stack: list[Screen] = field(default_factory=lambda: [Screen.LIBRARY])
    selected_book: str | None = None

    @property
    def screen(self) -> Screen:
        return self.stack[-1]

    def open(self, screen: Screen) -> None:
        if screen is Screen.LIBRARY:
            self.stack[:] = [Screen.LIBRARY]
        elif screen is not self.screen:
            self.stack.append(screen)

    def open_book(self, path: str) -> None:
        if not path:
            raise ValueError("book path is required")
        self.selected_book = path
        self.open(Screen.READER)

    def back(self) -> Screen:
        if len(self.stack) > 1:
            self.stack.pop()
        return self.screen
