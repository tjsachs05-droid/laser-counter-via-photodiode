"""Shots-per-second from the box's own pulse timestamps.

Rates come from box timestamps (µs), not from when lines arrive over USB, because USB delivery
jitters by milliseconds. Host time is only used to notice that pulses have stopped.
"""

from __future__ import annotations

from collections import deque


class RateMeter:
    def __init__(self, max_pulses: int = 21, max_age_s: float = 5.0, stale_after_s: float = 2.0):
        self._times: deque[int] = deque(maxlen=max_pulses)
        self._max_age_us = max_age_s * 1e6
        self._stale_after_s = stale_after_s
        self._last_host_s: float | None = None

    def clear(self) -> None:
        self._times.clear()
        self._last_host_s = None

    def add(self, t_us: int, host_s: float) -> None:
        if self._times and t_us <= self._times[-1]:
            self._times.clear()  # box rebooted, so its clock restarted
        self._times.append(t_us)
        self._last_host_s = host_s

    def rate(self, host_s: float) -> float | None:
        """Pulses per second, 0.0 once pulses have stopped, or None if there isn't enough data yet."""
        if self._last_host_s is None:
            return None
        times = self._times
        mean_interval_s = (times[-1] - times[0]) / (len(times) - 1) / 1e6 if len(times) >= 2 else 0.0
        if host_s - self._last_host_s > max(self._stale_after_s, 3 * mean_interval_s):
            return 0.0
        recent = [t for t in times if times[-1] - t <= self._max_age_us]
        if len(recent) < 2:
            return None
        return (len(recent) - 1) / ((recent[-1] - recent[0]) / 1e6)
