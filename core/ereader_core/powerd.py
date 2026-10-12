"""Minimal powerd service entry point.

The hardware backend is selected by the Device Port.  Until a port provides
one, this service runs the *development* backend, which controls no hardware.
"""
from __future__ import annotations

import argparse
import signal
import threading
import time
from collections.abc import Callable

from .power import DevelopmentPowerBackend, PowerController, PowerState


def run(controller: PowerController, should_stop: Callable[[], bool],
        sleep: Callable[[float], None], interval: float) -> None:
    while not should_stop():
        sleep(interval)
    controller.transition(PowerState.SHUTDOWN)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Alpine EReader OS power policy daemon")
    parser.add_argument("--interval", type=float, default=1.0, help="poll interval in seconds")
    parser.add_argument("--run-for", type=float, default=None,
                        help="exit after this many seconds (smoke tests)")
    args = parser.parse_args(argv)
    if args.interval <= 0:
        parser.error("--interval must be positive")
    stop = threading.Event()
    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGTERM, lambda _s, _f: stop.set())
        signal.signal(signal.SIGINT, lambda _s, _f: stop.set())
    deadline = None if args.run_for is None else time.monotonic() + args.run_for
    controller = PowerController(DevelopmentPowerBackend())
    run(controller,
        lambda: stop.is_set() or (deadline is not None and time.monotonic() >= deadline),
        time.sleep, args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
