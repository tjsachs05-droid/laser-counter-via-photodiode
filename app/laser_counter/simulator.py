"""A stand-in for the Pico firmware, with a pretend laser, for building and testing the app without hardware.

It speaks exactly the protocol in docs/protocol.md, so the app can't tell it apart from the real box.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable

from . import protocol as p

FIRMWARE_VERSION = "sim-0.1.0"


def _monotonic_us() -> int:
    return time.monotonic_ns() // 1000


class SimulatedFirmware:
    """Fires a laser at `rep_rate_hz`.

    Each shot's photodiode peak is drawn from a normal distribution around `pulse_mv`. A small fraction
    of shots are weak (`weak_mv`), like a misfire, so the threshold setting visibly matters.
    """

    def __init__(
        self,
        rep_rate_hz: float = 5.0,
        pulse_mv: float = -600.0,
        pulse_sd_mv: float = 40.0,
        weak_shot_fraction: float = 0.01,
        weak_mv: float = -150.0,
        clock_us: Callable[[], int] = _monotonic_us,
        seed: int | None = None,
    ):
        self.rep_rate_hz = rep_rate_hz
        self.pulse_mv = pulse_mv
        self.pulse_sd_mv = pulse_sd_mv
        self.weak_shot_fraction = weak_shot_fraction
        self.weak_mv = weak_mv
        self._clock = clock_us
        self._rng = random.Random(seed)
        self._boot_us = clock_us()

        self.running = False
        self.count = 0
        self.thr_mv = -400
        self.hold_us = 1000
        self._last_detect_us: int | None = None
        self._next_shot_us = self._shot_period_us()
        self._next_stat_us = 1_000_000

    def now_us(self) -> int:
        return self._clock() - self._boot_us

    def _shot_period_us(self) -> int:
        return round(1e6 / self.rep_rate_hz) if self.rep_rate_hz > 0 else 0

    def _status(self) -> str:
        return p.format_status(
            p.Status(
                running=self.running,
                count=self.count,
                thr_mv=self.thr_mv,
                hold_us=self.hold_us,
                t_us=self.now_us(),
                bias_mv=1500.0 + self._rng.gauss(0, 0.3),
                thr_meas_mv=self.thr_mv + self._rng.gauss(0, 0.5),
            )
        )

    def handle(self, line: str) -> list[str]:
        """Respond to one command line, the way the firmware would."""
        cmd, _, arg = line.strip().partition(" ")
        if cmd == p.ID_QUERY:
            return [f"ID laser-counter fw={FIRMWARE_VERSION}"]
        if cmd == p.STATUS_QUERY:
            return [self._status()]
        if cmd == p.START:
            self.running = True
        elif cmd == p.PAUSE:
            self.running = False
        elif cmd == p.RESET:
            self.count = 0
        elif cmd in ("THR", "HOLD"):
            validate = p.cmd_threshold if cmd == "THR" else p.cmd_holdoff
            try:
                value = int(arg)
                validate(value)
            except ValueError as exc:
                return [f"ERR {exc}"]
            if cmd == "THR":
                self.thr_mv = value
            else:
                self.hold_us = value
            return [f"OK {cmd} {value}", self._status()]
        else:
            return [f"ERR unknown command {line.strip()!r}"]
        return [f"OK {cmd}", self._status()]

    def poll(self) -> list[str]:
        """Emit lines for every shot and heartbeat that has come due since the last poll."""
        now = self.now_us()
        lines = []
        period = self._shot_period_us()
        while period and self._next_shot_us <= now:
            shot_us = self._next_shot_us + round(self._rng.gauss(0, 30))
            self._next_shot_us += period
            weak = self._rng.random() < self.weak_shot_fraction
            peak_mv = self.weak_mv if weak else self._rng.gauss(self.pulse_mv, self.pulse_sd_mv)
            if peak_mv > self.thr_mv:
                continue  # never dips below the threshold
            if self._last_detect_us is not None and shot_us - self._last_detect_us < self.hold_us:
                continue
            self._last_detect_us = shot_us
            if self.running:
                self.count += 1
            lines.append(p.format_event(p.Event(self.count, shot_us, self.running)))
        if now >= self._next_stat_us:
            self._next_stat_us = now + 1_000_000
            lines.append(self._status())
        return lines
