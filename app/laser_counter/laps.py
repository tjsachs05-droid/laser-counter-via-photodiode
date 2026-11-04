"""Laps: several shot counts kept at once, each with its own name, pause and reset, like a stopwatch's laps.

The box keeps one running total of every shot it detects. Each new shot is added to every lap that is
running, so laps need nothing from the firmware.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

MAX_LAPS = 9
MAX_NAME_LENGTH = 24


def clean_name(name: str) -> str:
    """Collapse runs of spaces and trim to MAX_NAME_LENGTH characters."""
    return " ".join(str(name).split())[:MAX_NAME_LENGTH].strip()


@dataclass(eq=False)  # laps are told apart by identity: two laps may share a name and a count
class Lap:
    name: str
    count: int = 0
    running: bool = True


class Laps:
    """The laps on screen, in order: always at least one, at most MAX_LAPS."""

    def __init__(self, laps: list[Lap] | None = None):
        self._laps = list(laps)[:MAX_LAPS] if laps else [Lap("Lap1")]

    def __iter__(self) -> Iterator[Lap]:
        return iter(self._laps)

    def __len__(self) -> int:
        return len(self._laps)

    def __getitem__(self, index: int) -> Lap:
        return self._laps[index]

    @property
    def can_add(self) -> bool:
        return len(self._laps) < MAX_LAPS

    @property
    def can_remove(self) -> bool:
        return len(self._laps) > 1

    @property
    def any_running(self) -> bool:
        return any(lap.running for lap in self._laps)

    def add(self) -> Lap | None:
        """Add a lap at the bottom, running from 0. Returns None if there are already MAX_LAPS."""
        if not self.can_add:
            return None
        lap = Lap(self._free_name())
        self._laps.append(lap)
        return lap

    def remove(self, lap: Lap) -> bool:
        """Delete a lap. The last one left can't be deleted."""
        if not self.can_remove or lap not in self._laps:
            return False
        self._laps.remove(lap)
        return True

    def rename(self, lap: Lap, name: str) -> str:
        """Rename a lap and return its name. A blank name leaves it unchanged."""
        name = clean_name(name)
        if name:
            lap.name = name
        return lap.name

    def add_shots(self, shots: int) -> None:
        for lap in self._laps:
            if lap.running:
                lap.count += shots

    def to_list(self) -> list[dict]:
        return [{"name": lap.name, "count": lap.count, "running": lap.running} for lap in self._laps]

    @classmethod
    def from_list(cls, items: object) -> Laps:
        """Rebuild saved laps, skipping anything malformed."""
        laps = []
        for item in items if isinstance(items, list) else []:
            try:
                lap = Lap(clean_name(item["name"]), int(item["count"]), bool(item["running"]))
            except (KeyError, TypeError, ValueError):
                continue
            if lap.name and lap.count >= 0:
                laps.append(lap)
        return cls(laps)

    def _free_name(self) -> str:
        """Lap<n> numbered by the new lap's position, or else the lowest Lap<n> not already taken."""
        taken = {lap.name.casefold() for lap in self._laps}
        for n in (len(self._laps) + 1, *range(1, MAX_LAPS + 1)):
            if f"lap{n}" not in taken:
                return f"Lap{n}"
        return f"Lap{len(self._laps) + 1}"  # not reached: fewer than MAX_LAPS laps leave a number free


class ShotTally:
    """Turns the box's running total of shots into the number of new shots since the last reading.

    `mark` is (total, box clock in µs) at the last reading. Saved with the laps, it lets shots the box
    counted while the app was closed be added on the next connection, as long as the box stayed powered.
    """

    def __init__(self, mark: tuple[int, int] | None = None):
        self.mark = mark
        self._synced = False

    def reconnected(self) -> None:
        """The next reading decides whether the box kept counting since `mark`."""
        self._synced = False

    def update(self, count: int, t_us: int, running: bool) -> int:
        mark, self.mark = self.mark, (count, t_us)
        if not self._synced:
            self._synced = True
            # A box that restarted has its clock and total back at 0, and it powers up paused.
            same_power_up = mark is not None and running and t_us >= mark[1] and count >= mark[0]
            return count - mark[0] if same_power_up else 0
        return count - mark[0] if count >= mark[0] else count
