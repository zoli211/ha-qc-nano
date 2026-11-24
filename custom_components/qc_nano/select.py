"""Select entities for QC nano."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import COOLING_MODES
from .coordinator import QcNanoConfigEntry
from .entity import QcNanoEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QcNanoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select entities."""
    coordinator = entry.runtime_data
    async_add_entities(QcNanoCoolingMode(coordinator, d) for d in coordinator.data)


class QcNanoCoolingMode(QcNanoEntity, SelectEntity):
    """Cooling mode: off, standard or boost."""

    _attr_translation_key = "cooling_mode"
    _attr_options = list(COOLING_MODES)
    _attr_icon = "mdi:snowflake"

    def __init__(self, coordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "cooling_mode")

    @property
    def current_option(self) -> str | None:
        value = self.device.settings.get("cooling")
        value = value.lower() if isinstance(value, str) else None
        return value if value in COOLING_MODES else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_update_settings(
            self._device_id, local={"cooling": option}, coolingMode=option.upper()
        )
