"""The small, testable power-policy state machine.

Hardware writes are deliberately delegated to a backend.  The development
backend is observable but makes no claim to control a physical radio or panel.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class PowerState(str, Enum):
    ACTIVE = "active"
    READING = "reading"
    IDLE = "idle"
    SUSPEND = "suspend"
    SHUTDOWN = "shutdown"


class PowerBackend(Protocol):
    def set_radios_blocked(self, blocked: bool) -> None: ...
    def set_display(self, enabled: bool, dimmed: bool = False) -> None: ...
    def suspend(self) -> None: ...
    def shutdown(self) -> None: ...


@dataclass
class DevelopmentPowerBackend:
    """A host-only backend used by tests and the development shell."""
    radios_blocked: bool = True
    display_enabled: bool = True
    display_dimmed: bool = False
    suspended: bool = False
    shutdown_requested: bool = False

    def set_radios_blocked(self, blocked: bool) -> None:
        self.radios_blocked = blocked

    def set_display(self, enabled: bool, dimmed: bool = False) -> None:
        self.display_enabled, self.display_dimmed = enabled, dimmed

    def suspend(self) -> None:
        self.suspended = True

    def shutdown(self) -> None:
        self.shutdown_requested = True


class PowerController:
    """Enforces the architecture rule that reading is offline."""
    def __init__(self, backend: PowerBackend) -> None:
        self.backend = backend
        self.state = PowerState.ACTIVE
        self.wifi_pinned = False
        self.backend.set_radios_blocked(True)

    def transition(self, state: PowerState) -> None:
        self.state = state
        if state is PowerState.READING:
            self.wifi_pinned = False
            self.backend.set_radios_blocked(True)
            self.backend.set_display(True)
        elif state is PowerState.ACTIVE:
            self.backend.set_display(True)
        elif state is PowerState.IDLE:
            self.backend.set_radios_blocked(True)
            self.backend.set_display(True, dimmed=True)
        elif state is PowerState.SUSPEND:
            self.backend.set_radios_blocked(True)
            self.backend.set_display(False)
            self.backend.suspend()
        elif state is PowerState.SHUTDOWN:
            self.backend.set_radios_blocked(True)
            self.backend.set_display(False)
            self.backend.shutdown()

    def request_wifi(self, enabled: bool, *, pin: bool = False) -> bool:
        """Returns False when policy refuses a radio request."""
        if enabled and self.state in {PowerState.READING, PowerState.IDLE, PowerState.SUSPEND, PowerState.SHUTDOWN}:
            return False
        self.wifi_pinned = enabled and pin
        self.backend.set_radios_blocked(not enabled)
        return True
