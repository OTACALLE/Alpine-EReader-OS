"""The small, testable power-policy state machine (ARCHITECTURE.md §21).

Hardware writes are delegated to a backend.  The development backend is
observable but makes no claim to control a physical radio or panel.

Main states follow §21.2.  RESUME is the transient state entered when leaving
SUSPEND.  LOW and CRITICAL battery are *modifiers*, not exclusive states
(§21.2: "a modifier state, not exclusive with READING/IDLE"), modelled by
``BatteryLevel``.
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
    RESUME = "resume"
    SHUTDOWN = "shutdown"


class BatteryLevel(str, Enum):
    NORMAL = "normal"
    LOW = "low"
    CRITICAL = "critical"


# Provisional thresholds: the architecture defines the levels but no numbers.
# They must be replaced by measured values from the device port (Phase 5).
LOW_BATTERY_PERCENT = 15
CRITICAL_BATTERY_PERCENT = 5


def battery_level_for(percent: int, charging: bool) -> BatteryLevel:
    if not 0 <= percent <= 100:
        raise ValueError("battery percent must be between 0 and 100")
    if charging:
        return BatteryLevel.NORMAL
    if percent <= CRITICAL_BATTERY_PERCENT:
        return BatteryLevel.CRITICAL
    if percent <= LOW_BATTERY_PERCENT:
        return BatteryLevel.LOW
    return BatteryLevel.NORMAL


class InvalidTransition(ValueError):
    """Raised for a power-state transition the policy forbids."""


_ALL_LIVE = {PowerState.ACTIVE, PowerState.READING, PowerState.IDLE,
             PowerState.SUSPEND, PowerState.SHUTDOWN}
ALLOWED_TRANSITIONS: dict[PowerState, frozenset[PowerState]] = {
    PowerState.ACTIVE: frozenset(_ALL_LIVE - {PowerState.ACTIVE}),
    PowerState.READING: frozenset(_ALL_LIVE - {PowerState.READING}),
    PowerState.IDLE: frozenset(_ALL_LIVE - {PowerState.IDLE}),
    # Leaving SUSPEND must go through RESUME; SUSPEND -> ACTIVE/READING is forbidden.
    PowerState.SUSPEND: frozenset({PowerState.RESUME, PowerState.SHUTDOWN}),
    PowerState.RESUME: frozenset(_ALL_LIVE - {PowerState.RESUME}),
    PowerState.SHUTDOWN: frozenset(),
}
# While the battery is CRITICAL only these are allowed (§21.2: auto SUSPEND/SHUTDOWN).
CRITICAL_ALLOWED = frozenset({PowerState.SUSPEND, PowerState.RESUME, PowerState.SHUTDOWN})


class PowerBackend(Protocol):
    def set_radios_blocked(self, blocked: bool) -> None: ...
    def set_display(self, enabled: bool, dimmed: bool = False) -> None: ...
    def suspend(self) -> None: ...
    def resume(self) -> None: ...
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

    def resume(self) -> None:
        self.suspended = False

    def shutdown(self) -> None:
        self.shutdown_requested = True


class PowerController:
    """Enforces the architecture rule that reading is offline."""

    def __init__(self, backend: PowerBackend) -> None:
        self.backend = backend
        self.state = PowerState.ACTIVE
        self.battery = BatteryLevel.NORMAL
        self.wifi_pinned = False
        self.backend.set_radios_blocked(True)

    @property
    def _dimmed(self) -> bool:
        return self.battery is not BatteryLevel.NORMAL

    def transition(self, state: PowerState) -> None:
        if state is self.state:
            return
        if state not in ALLOWED_TRANSITIONS[self.state]:
            raise InvalidTransition(f"{self.state.value} -> {state.value} is not allowed")
        if self.battery is BatteryLevel.CRITICAL and state not in CRITICAL_ALLOWED:
            raise InvalidTransition(f"{state.value} is refused while the battery is critical")
        self._enter(state)

    def _enter(self, state: PowerState) -> None:
        self.state = state
        # Radio requests never survive leaving ACTIVE.
        self.wifi_pinned = False
        if state is PowerState.ACTIVE:
            self.backend.set_display(True, dimmed=self._dimmed)
            return
        self.backend.set_radios_blocked(True)
        if state in (PowerState.READING, PowerState.RESUME):
            self.backend.set_display(True, dimmed=self._dimmed)
            if state is PowerState.RESUME:
                self.backend.resume()
        elif state is PowerState.IDLE:
            self.backend.set_display(True, dimmed=True)
        elif state is PowerState.SUSPEND:
            self.backend.set_display(False)
            self.backend.suspend()
        elif state is PowerState.SHUTDOWN:
            self.backend.set_display(False)
            self.backend.shutdown()

    def set_battery_level(self, level: BatteryLevel) -> None:
        """Apply the LOW/CRITICAL modifier; CRITICAL forces radios off and sleeps."""
        self.battery = level
        if level is BatteryLevel.NORMAL:
            if self.state in (PowerState.ACTIVE, PowerState.READING, PowerState.RESUME):
                self.backend.set_display(True, dimmed=False)
            return
        if level is BatteryLevel.CRITICAL:
            self.wifi_pinned = False
            self.backend.set_radios_blocked(True)
            if self.state not in (PowerState.SUSPEND, PowerState.SHUTDOWN):
                self._enter(PowerState.SUSPEND)
            return
        if self.state in (PowerState.ACTIVE, PowerState.READING, PowerState.RESUME):
            self.backend.set_display(True, dimmed=True)

    def request_wifi(self, enabled: bool, *, pin: bool = False) -> bool:
        """Returns False when policy refuses a radio request (§21.2)."""
        if enabled and (self.state is not PowerState.ACTIVE or self.battery is BatteryLevel.CRITICAL):
            return False
        self.wifi_pinned = enabled and pin
        self.backend.set_radios_blocked(not enabled)
        return True
