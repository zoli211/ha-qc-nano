"""Sensors for QC nano."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import QcNanoConfigEntry, QcNanoDevice
from .entity import QcNanoEntity

PARALLEL_UPDATES = 0


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _liters(value: Any) -> float | None:
    """API volumes are in millilitres."""
    number = _num(value)
    return None if number is None else round(number / 1000, 3)


def _ts(value: Any) -> datetime | None:
    return dt_util.parse_datetime(value) if isinstance(value, str) else None


def _path(data: dict[str, Any] | None, *keys: str) -> Any:
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def _lower(value: Any) -> str | None:
    return value.lower() if isinstance(value, str) and value else None


def _health(device: QcNanoDevice) -> str:
    """Same rule the official app uses."""
    statuses = (device.cloud.get("cleaningStatus"), _path(device.cloud, "filter", "status"))
    if "Poor" in statuses:
        return "bad"
    if "Warning" in statuses:
        return "poor"
    return "good"


def _cold_temp(device: QcNanoDevice) -> float | None:
    for value in (
        _path(device.live, "temperatures", "cold_water"),
        device.info.get("cold_water_temp"),
        device.cloud.get("coldWaterTemp"),
    ):
        if (number := _num(value)) is not None:
            return number
    return None


def _filter_remaining(device: QcNanoDevice) -> float | None:
    used = _num(_path(device.cloud, "filter", "usedVolume"))
    total = _num(_path(device.cloud, "filter", "maxVolume"))
    if used is None or not total:
        return None
    return round(max(0.0, (total - used) / total * 100), 1)


def _live(*keys: str) -> Callable[[QcNanoDevice], Any]:
    return lambda d: _num(_path(d.live, *keys))


@dataclass(frozen=True, kw_only=True)
class QcNanoSensorDescription(SensorEntityDescription):
    """Describes a QC nano sensor."""

    value_fn: Callable[[QcNanoDevice], Any]
    live: bool = False


LEVEL_OPTIONS = ["good", "warning", "poor"]
VOLUME = {
    "device_class": SensorDeviceClass.WATER,
    "native_unit_of_measurement": UnitOfVolume.LITERS,
    "state_class": SensorStateClass.TOTAL_INCREASING,
    "suggested_display_precision": 1,
}
TEMPERATURE = {
    "device_class": SensorDeviceClass.TEMPERATURE,
    "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
    "state_class": SensorStateClass.MEASUREMENT,
}
HOURS = {
    "device_class": SensorDeviceClass.DURATION,
    "native_unit_of_measurement": UnitOfTime.HOURS,
    "state_class": SensorStateClass.TOTAL_INCREASING,
    "entity_category": EntityCategory.DIAGNOSTIC,
}

SENSORS: tuple[QcNanoSensorDescription, ...] = (
    # temperatures
    QcNanoSensorDescription(key="cold_water_temperature", value_fn=_cold_temp, **TEMPERATURE),
    QcNanoSensorDescription(
        key="hot_water_temperature",
        value_fn=_live("temperatures", "hot_water"),
        live=True,
        **TEMPERATURE,
    ),
    QcNanoSensorDescription(
        key="board_temperature",
        value_fn=_live("temperatures", "on_board"),
        live=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        **TEMPERATURE,
    ),
    # consumption
    QcNanoSensorDescription(
        key="water_today",
        value_fn=lambda d: _liters(
            sum(_num(d.today.get(k)) or 0 for k in ("coldWater", "hotWater", "ambientWater"))
        )
        if d.today
        else None,
        **VOLUME,
    ),
    QcNanoSensorDescription(
        key="cold_water_today", value_fn=lambda d: _liters(d.today.get("coldWater")), **VOLUME
    ),
    QcNanoSensorDescription(
        key="hot_water_today", value_fn=lambda d: _liters(d.today.get("hotWater")), **VOLUME
    ),
    QcNanoSensorDescription(
        key="ambient_water_today",
        value_fn=lambda d: _liters(d.today.get("ambientWater")),
        **VOLUME,
    ),
    QcNanoSensorDescription(
        key="water_total", value_fn=lambda d: _liters(d.cloud.get("usedVolume")), **VOLUME
    ),
    QcNanoSensorDescription(
        key="cold_water_total",
        value_fn=lambda d: _liters(_path(d.cloud, "summary", "coldWater")),
        **VOLUME,
    ),
    QcNanoSensorDescription(
        key="hot_water_total",
        value_fn=lambda d: _liters(_path(d.cloud, "summary", "hotWater")),
        **VOLUME,
    ),
    QcNanoSensorDescription(
        key="ambient_water_total",
        value_fn=lambda d: _liters(_path(d.cloud, "summary", "ambientWater")),
        **VOLUME,
    ),
    # usage since the last filter change, reported by the device itself
    QcNanoSensorDescription(
        key="cold_water_filter_period",
        value_fn=_live("usage", "cold"),
        live=True,
        **VOLUME,
    ),
    QcNanoSensorDescription(
        key="hot_water_filter_period", value_fn=_live("usage", "hot"), live=True, **VOLUME
    ),
    QcNanoSensorDescription(
        key="ambient_water_filter_period",
        value_fn=_live("usage", "ambient"),
        live=True,
        **VOLUME,
    ),
    # filter
    QcNanoSensorDescription(
        key="filter_used",
        value_fn=lambda d: _liters(_path(d.cloud, "filter", "usedVolume")),
        **VOLUME,
    ),
    QcNanoSensorDescription(
        key="filter_capacity",
        value_fn=lambda d: _liters(_path(d.cloud, "filter", "maxVolume")),
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    QcNanoSensorDescription(
        key="filter_remaining",
        value_fn=_filter_remaining,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    QcNanoSensorDescription(
        key="filter_status",
        value_fn=lambda d: _lower(_path(d.cloud, "filter", "status")),
        device_class=SensorDeviceClass.ENUM,
        options=LEVEL_OPTIONS,
    ),
    QcNanoSensorDescription(
        key="next_filter_change",
        value_fn=lambda d: _ts(_path(d.cloud, "filter", "nextFilterChange")),
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    QcNanoSensorDescription(
        key="last_filter_change",
        value_fn=lambda d: _ts(d.cloud.get("lastFilterChange")),
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    QcNanoSensorDescription(
        key="filter_life",
        value_fn=lambda d: _path(d.cloud, "filter", "filterLife"),
        native_unit_of_measurement=UnitOfTime.MONTHS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    QcNanoSensorDescription(
        key="filter_months_used",
        value_fn=lambda d: _path(d.cloud, "filter", "usedInMonths"),
        native_unit_of_measurement=UnitOfTime.MONTHS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    QcNanoSensorDescription(
        key="filter_first_use",
        value_fn=lambda d: _ts(_path(d.cloud, "filter", "firstOperationDate")),
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # cleaning / health
    QcNanoSensorDescription(
        key="cleaning_status",
        value_fn=lambda d: _lower(d.cloud.get("cleaningStatus")),
        device_class=SensorDeviceClass.ENUM,
        options=LEVEL_OPTIONS,
    ),
    QcNanoSensorDescription(
        key="next_cleaning",
        value_fn=lambda d: _ts(d.cloud.get("nextCleaning")),
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    QcNanoSensorDescription(
        key="last_cleaning",
        value_fn=lambda d: _ts(d.cloud.get("lastFilterClean")),
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    QcNanoSensorDescription(
        key="system_health",
        value_fn=_health,
        device_class=SensorDeviceClass.ENUM,
        options=["good", "poor", "bad"],
    ),
    QcNanoSensorDescription(
        key="hygiene_days",
        value_fn=lambda d: _num(_path(d.info, "hygiene", "days")),
        live=True,
        native_unit_of_measurement=UnitOfTime.DAYS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # hardware (live)
    QcNanoSensorDescription(
        key="fan_speed",
        value_fn=lambda d: _num(((d.live.get("fans") or [{}])[0] or {}).get("rpm")),
        live=True,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    QcNanoSensorDescription(
        key="fan_power",
        value_fn=lambda d: _num(((d.live.get("fans") or [{}])[0] or {}).get("power")),
        live=True,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    QcNanoSensorDescription(
        key="operating_hours", value_fn=_live("system_operation", "total_unit", "hours"), live=True, **HOURS
    ),
    QcNanoSensorDescription(
        key="cooling_hours", value_fn=_live("system_operation", "cooling_unit", "hours"), live=True, **HOURS
    ),
    QcNanoSensorDescription(
        key="heating_hours", value_fn=_live("system_operation", "heating_unit", "hours"), live=True, **HOURS
    ),
    QcNanoSensorDescription(
        key="cold_valve_cycles",
        value_fn=_live("valves", "cold", "lifetime"),
        live=True,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    QcNanoSensorDescription(
        key="hot_valve_cycles",
        value_fn=_live("valves", "hot", "lifetime"),
        live=True,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    QcNanoSensorDescription(
        key="ambient_valve_cycles",
        value_fn=_live("valves", "ambient", "lifetime"),
        live=True,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    QcNanoSensorDescription(
        key="wifi_signal",
        value_fn=lambda d: _num(d.info.get("wifi_rssi")),
        live=True,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # connection / misc
    QcNanoSensorDescription(
        key="last_disconnect",
        value_fn=lambda d: _ts(d.cloud.get("disconnectedAt")),
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    QcNanoSensorDescription(
        key="live_updated",
        value_fn=lambda d: d.live_updated.replace(second=0, microsecond=0)
        if d.live_updated
        else None,
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    QcNanoSensorDescription(
        key="activated",
        value_fn=lambda d: _ts(d.cloud.get("activatedAt")),
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    QcNanoSensorDescription(
        key="registration_status",
        value_fn=lambda d: _lower(d.cloud.get("status")),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QcNanoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        QcNanoSensor(coordinator, device_id, description)
        for device_id in coordinator.data
        for description in SENSORS
    )


class QcNanoSensor(QcNanoEntity, SensorEntity):
    """A QC nano sensor."""

    entity_description: QcNanoSensorDescription

    def __init__(self, coordinator, device_id: str, description: QcNanoSensorDescription) -> None:
        super().__init__(coordinator, device_id, description.key)
        self.entity_description = description
        self._attr_translation_key = description.key

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        if self.entity_description.live:
            return self.native_value is not None
        return True

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.device)
