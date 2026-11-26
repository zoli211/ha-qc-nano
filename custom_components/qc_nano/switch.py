"""Switches for QC nano settings."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, SLIDER_LEVELS, SLIDERS
from .coordinator import QcNanoConfigEntry, QcNanoDevice, read_slider
from .energy_saver import parse_schedule
from .entity import QcNanoEntity

PARALLEL_UPDATES = 1


def _read_schedule(device: QcNanoDevice) -> str:
    """Return the energy saver schedule exactly as read; never a default."""
    raw = device.settings.get("energySaver")
    if parse_schedule(raw) is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="schedule_not_loaded"
        )
    return raw


@dataclass(frozen=True, kw_only=True)
class QcNanoSwitchDescription(SwitchEntityDescription):
    """A boolean device setting."""

    setting: str
    param: str
    to_param: Callable[[bool, QcNanoDevice], Any] = lambda value, device: value
    available_fn: Callable[[QcNanoDevice], bool] = lambda device: True


SWITCHES: tuple[QcNanoSwitchDescription, ...] = (
    QcNanoSwitchDescription(
        key="child_lock", setting="childLock", param="childLock", icon="mdi:lock"
    ),
    QcNanoSwitchDescription(
        key="light_off", setting="lightOff", param="lightOff", icon="mdi:lightbulb-off"
    ),
    QcNanoSwitchDescription(
        key="energy_saver",
        setting="energySaverStatus",
        param="energySaver",
        icon="mdi:leaf",
        to_param=lambda value, device: {
            "enabled": value,
            "settings": _read_schedule(device),
        },
        available_fn=lambda device: (
            parse_schedule(device.settings.get("energySaver")) is not None
        ),
    ),
    QcNanoSwitchDescription(
        key="volume_sliders",
        setting="volumeSliderStatus",
        param="volumeSliderStatus",
        icon="mdi:cup-water",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QcNanoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switches."""
    coordinator = entry.runtime_data
    entities: list[SwitchEntity] = []
    for device_id in coordinator.data:
        entities.extend(
            QcNanoSettingSwitch(coordinator, device_id, description)
            for description in SWITCHES
        )
        entities.extend(
            QcNanoSliderLevelSwitch(coordinator, device_id, kind, level)
            for kind in SLIDERS
            for level in SLIDER_LEVELS
        )
    async_add_entities(entities)


class QcNanoSettingSwitch(QcNanoEntity, SwitchEntity):
    """A boolean setting of the dispenser."""

    entity_description: QcNanoSwitchDescription

    def __init__(self, coordinator, device_id: str, description: QcNanoSwitchDescription) -> None:
        super().__init__(coordinator, device_id, description.key)
        self.entity_description = description
        self._attr_translation_key = description.key

    @property
    def available(self) -> bool:
        return super().available and self.entity_description.available_fn(self.device)

    @property
    def is_on(self) -> bool | None:
        value = self.device.settings.get(self.entity_description.setting)
        return None if value is None else bool(value)

    async def _async_set(self, value: bool) -> None:
        desc = self.entity_description
        await self.coordinator.async_update_settings(
            self._device_id,
            local={desc.setting: value},
            **{desc.param: desc.to_param(value, self.device)},
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set(False)


class QcNanoSliderLevelSwitch(QcNanoEntity, SwitchEntity):
    """Enables or disables one portion size button of a tap."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:cup-outline"

    def __init__(self, coordinator, device_id: str, kind: str, level: str) -> None:
        super().__init__(coordinator, device_id, f"{kind}_{level}_enabled")
        self._kind = kind
        self._level = level
        self._attr_translation_key = f"{kind}_{level}_enabled"

    @property
    def available(self) -> bool:
        return super().available and read_slider(self.device, self._kind) is not None

    @property
    def is_on(self) -> bool | None:
        slider = read_slider(self.device, self._kind)
        return None if slider is None else slider[self._level]["status"]

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_slider_level(
            self._device_id, self._kind, self._level, status=True
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_slider_level(
            self._device_id, self._kind, self._level, status=False
        )
