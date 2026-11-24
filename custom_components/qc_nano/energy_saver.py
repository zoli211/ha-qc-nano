"""Parse and build the energy saver ("active hours") schedule string.

The cloud stores it as e.g. ``mo:1:6-24;tu:1:6-12,14-22;...;su:0:0-0;`` where
the middle field tells whether the day is enabled and the last field lists
hour ranges.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re

from .const import WEEKDAYS

RANGE_RE = re.compile(r"^\s*(\d{1,2})\s*-\s*(\d{1,2})\s*$")
OFF_WORDS = {"", "off", "ki", "-", "none"}


@dataclass
class DaySchedule:
    """One day of the schedule."""

    enabled: bool = True
    ranges: list[tuple[int, int]] = field(default_factory=lambda: [(0, 24)])

    def to_text(self) -> str:
        if not self.enabled:
            return "off"
        return ",".join(f"{a}-{b}" for a, b in self.ranges) or "off"


@dataclass
class Schedule:
    """The whole week."""

    days: dict[str, DaySchedule]

    def to_string(self) -> str:
        out = ""
        for day in WEEKDAYS:
            sched = self.days[day]
            ranges = ",".join(f"{a}-{b}" for a, b in sched.ranges) or "0-0"
            out += f"{day}:{1 if sched.enabled else 0}:{ranges};"
        return out


def parse_ranges(text: str) -> list[tuple[int, int]]:
    """Parse ``6-12,14-22``; raise ValueError when invalid."""
    ranges: list[tuple[int, int]] = []
    for part in text.split(","):
        match = RANGE_RE.match(part)
        if not match:
            raise ValueError(f"Invalid hour range: {part!r}")
        start, end = int(match.group(1)), int(match.group(2))
        if not 0 <= start < end <= 24:
            raise ValueError(f"Invalid hour range: {part!r}")
        ranges.append((start, end))
    return ranges


def parse_schedule(value: str | None) -> Schedule:
    """Parse the cloud string; unknown or missing days default to 0-24."""
    days = {day: DaySchedule() for day in WEEKDAYS}
    for chunk in (value or "").split(";"):
        parts = chunk.strip().split(":")
        if len(parts) != 3 or parts[0] not in days:
            continue
        try:
            ranges = [] if parts[2] in ("", "0-0") else parse_ranges(parts[2])
        except ValueError:
            ranges = []
        days[parts[0]] = DaySchedule(enabled=parts[1] == "1", ranges=ranges)
    return Schedule(days)


def apply_day_text(schedule: Schedule, day: str, text: str) -> Schedule:
    """Apply a user-entered value (``off`` or ranges) to one day."""
    cleaned = text.strip().lower()
    current = schedule.days[day]
    if cleaned in OFF_WORDS:
        schedule.days[day] = DaySchedule(enabled=False, ranges=current.ranges)
    else:
        schedule.days[day] = DaySchedule(enabled=True, ranges=parse_ranges(cleaned))
    return schedule
