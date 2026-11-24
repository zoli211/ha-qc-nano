"""Number entities for QC nano settings."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import COLD_TEMP_MAX, COLD_TEMP_MIN, SLIDER_LEVELS, SLIDERS
from .coordinator import QcNanoConfigEntry
from .entity import QcNanoEntity

PARALLEL_UPDATES = 1

PORTION_MIN = 50
PORTION_MAX = 3000
PORTION_STEP = 10


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QcNanoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number entities."""
    coordinator = entry.runtime_data
    entities: list[NumberEntity] = []
    for device_id in coordinator.data:
        entities.append(QcNanoColdTemperature(coordinator, device_id))
        entities.extend(
            QcNanoPortion(coordinator, device_id, kind, level)
            for kind in SLIDERS
            for level in SLIDER_LEVELS
        )
    async_add_entities(entities)


class QcNanoColdTemperature(QcNanoEntity, NumberEntity):
    """Target temperature of the cold water."""

    _attr_translation_key = "cold_temperature"
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = COLD_TEMP_MIN
    _attr_native_max_value = COLD_TEMP_MAX
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "cold_temperature")

    @property
    def native_value(self) -> float | None:
        return self.device.settings.get("coldTemperature")

    async def async_set_native_value(self, value: float) -> None:
        temp = int(round(value))
        await self.coordinator.async_update_settings(
            self._device_id, local={"coldTemperature": temp}, coldTemperature=temp
        )


class QcNanoPortion(QcNanoEntity, NumberEntity):
    """Volume of one portion button of a tap."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = NumberDeviceClass.VOLUME
    _attr_native_unit_of_measurement = UnitOfVolume.MILLILITERS
    _attr_native_min_value = PORTION_MIN
    _attr_native_max_value = PORTION_MAX
    _attr_native_step = PORTION_STEP
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:cup-water"

    def __init__(self, coordinator, device_id: str, kind: str, level: str) -> None:
        super().__init__(coordinator, device_id, f"{kind}_{level}_volume")
        self._kind = kind
        self._level = level
        self._attr_translation_key = f"{kind}_{level}_volume"

    @property
    def native_value(self) -> float | None:
        slider = self.device.settings.get(SLIDERS[self._kind][0]) or {}
        return (slider.get(self._level) or {}).get("value")

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_slider_level(
            self._device_id, self._kind, self._level, value=int(round(value))
        )
