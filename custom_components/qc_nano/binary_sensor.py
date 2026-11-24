"""Binary sensors for QC nano."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import QcNanoConfigEntry, QcNanoCoordinator, QcNanoDevice
from .entity import QcNanoEntity

PARALLEL_UPDATES = 0


def _status(device: QcNanoDevice, *keys: str, on: str | tuple[str, ...]) -> bool | None:
    data: Any = device.live
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    if not isinstance(data, str):
        return None
    return data.lower() in ((on,) if isinstance(on, str) else on)


def _not_good(value: Any) -> bool | None:
    return None if not isinstance(value, str) else value != "Good"


@dataclass(frozen=True, kw_only=True)
class QcNanoBinaryDescription(BinarySensorEntityDescription):
    """Describes a QC nano binary sensor."""

    value_fn: Callable[[QcNanoDevice, QcNanoCoordinator], bool | None]


BINARY_SENSORS: tuple[QcNanoBinaryDescription, ...] = (
    QcNanoBinaryDescription(
        key="cloud_connection",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda d, c: d.connected,
    ),
    QcNanoBinaryDescription(
        key="live_connection",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d, c: bool(c.mqtt and c.mqtt.connected),
    ),
    QcNanoBinaryDescription(
        key="power",
        device_class=BinarySensorDeviceClass.POWER,
        value_fn=lambda d, c: _status(d, "system_operation", "total_unit", "status", on="on"),
    ),
    QcNanoBinaryDescription(
        key="cooling",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda d, c: _status(d, "system_operation", "cooling_unit", "status", on="on"),
    ),
    QcNanoBinaryDescription(
        key="heating",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda d, c: _status(d, "system_operation", "heating_unit", "status", on="on"),
    ),
    QcNanoBinaryDescription(
        key="cold_valve",
        device_class=BinarySensorDeviceClass.OPENING,
        value_fn=lambda d, c: _status(d, "valves", "cold", "status", on=("open", "opened")),
    ),
    QcNanoBinaryDescription(
        key="hot_valve",
        device_class=BinarySensorDeviceClass.OPENING,
        value_fn=lambda d, c: _status(d, "valves", "hot", "status", on=("open", "opened")),
    ),
    QcNanoBinaryDescription(
        key="ambient_valve",
        device_class=BinarySensorDeviceClass.OPENING,
        value_fn=lambda d, c: _status(d, "valves", "ambient", "status", on=("open", "opened")),
    ),
    QcNanoBinaryDescription(
        key="filter_problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d, c: _not_good((d.cloud.get("filter") or {}).get("status")),
    ),
    QcNanoBinaryDescription(
        key="cleaning_problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d, c: _not_good(d.cloud.get("cleaningStatus")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QcNanoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        QcNanoBinarySensor(coordinator, device_id, description)
        for device_id in coordinator.data
        for description in BINARY_SENSORS
    )


class QcNanoBinarySensor(QcNanoEntity, BinarySensorEntity):
    """A QC nano binary sensor."""

    entity_description: QcNanoBinaryDescription

    def __init__(self, coordinator, device_id: str, description: QcNanoBinaryDescription) -> None:
        super().__init__(coordinator, device_id, description.key)
        self.entity_description = description
        self._attr_translation_key = description.key

    @property
    def available(self) -> bool:
        return super().available and self.is_on is not None

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.device, self.coordinator)
