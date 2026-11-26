"""Parse and build the energy saver ("active hours") schedule string.

The cloud stores it as e.g. ``mo:1:6-24;tu:1:6-12,14-22;...;su:0:0-0;`` where
the middle field tells whether the day is enabled and the last field lists
hour ranges.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from .const import WEEKDAYS

RANGE_RE = re.compile(r"^\s*(\d{1,2})\s*-\s*(\d{1,2})\s*$")
OFF_WORDS = {"", "off", "ki", "-", "none"}


@dataclass
class DaySchedule:
    """One day of the schedule."""

    enabled: bool
    ranges: list[tuple[int, int]]

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


def parse_schedule(value: str | None) -> Schedule | None:
    """Parse the cloud string; return None unless all seven days are valid.

    The schedule is always written back as a whole week, so a missing or
    malformed day must not be replaced by a made-up default.
    """
    days: dict[str, DaySchedule] = {}
    for chunk in (value or "").split(";"):
        if not chunk.strip():
            continue
        parts = chunk.strip().split(":")
        if len(parts) != 3 or parts[0] not in WEEKDAYS or parts[1] not in ("0", "1"):
            return None
        try:
            ranges = [] if parts[2] in ("", "0-0") else parse_ranges(parts[2])
        except ValueError:
            return None
        days[parts[0]] = DaySchedule(enabled=parts[1] == "1", ranges=ranges)
    if set(days) != set(WEEKDAYS):
        return None
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
