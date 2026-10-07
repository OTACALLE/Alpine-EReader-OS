"""Minimal service entry point; hardware backend selection belongs to Device Ports."""
from __future__ import annotations

import signal
import time

from .power import DevelopmentPowerBackend, PowerController, PowerState


def main() -> int:
    controller = PowerController(DevelopmentPowerBackend())
    running = True

    def stop(_signal: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while running:
        time.sleep(1)
    controller.transition(PowerState.SHUTDOWN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
