"""Energy saver schedule (one text entity per weekday)."""

from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, WEEKDAYS
from .coordinator import QcNanoConfigEntry
from .energy_saver import apply_day_text, parse_schedule
from .entity import QcNanoEntity

PARALLEL_UPDATES = 1

# "off" / "ki" / "-" or comma separated hour ranges such as 6-12,14-22
PATTERN = r"^\s*((off|ki|-)|\d{1,2}\s*-\s*\d{1,2}(\s*,\s*\d{1,2}\s*-\s*\d{1,2})*)\s*$"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QcNanoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the schedule text entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        QcNanoScheduleDay(coordinator, device_id, day)
        for device_id in coordinator.data
        for day in WEEKDAYS
    )


class QcNanoScheduleDay(QcNanoEntity, TextEntity):
    """Active hours of the energy saver for one weekday."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:calendar-clock"
    _attr_pattern = PATTERN
    _attr_native_max = 100

    def __init__(self, coordinator, device_id: str, day: str) -> None:
        super().__init__(coordinator, device_id, f"active_hours_{day}")
        self._day = day
        self._attr_translation_key = f"active_hours_{day}"

    @property
    def native_value(self) -> str | None:
        raw = self.device.settings.get("energySaver")
        if raw is None:
            return None
        return parse_schedule(raw).days[self._day].to_text()

    async def async_set_value(self, value: str) -> None:
        settings = self.device.settings
        schedule = parse_schedule(settings.get("energySaver"))
        try:
            apply_day_text(schedule, self._day, value)
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_hours",
                translation_placeholders={"value": value},
            ) from err
        new = schedule.to_string()
        enabled = bool(settings.get("energySaverStatus"))
        await self.coordinator.async_update_settings(
            self._device_id,
            local={"energySaver": new},
            energySaver={"enabled": enabled, "settings": new},
        )
