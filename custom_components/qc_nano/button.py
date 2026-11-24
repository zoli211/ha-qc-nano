"""Buttons for QC nano."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import QcNanoConfigEntry, QcNanoCoordinator
from .entity import QcNanoEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class QcNanoButtonDescription(ButtonEntityDescription):
    """Describes a QC nano button."""

    press_fn: Callable[[QcNanoCoordinator, str], Awaitable[None]]


BUTTONS: tuple[QcNanoButtonDescription, ...] = (
    QcNanoButtonDescription(
        key="refresh",
        icon="mdi:refresh",
        entity_category=EntityCategory.DIAGNOSTIC,
        press_fn=lambda c, d: c.async_refresh_now(d),
    ),
    QcNanoButtonDescription(
        key="reset_filter",
        icon="mdi:filter-check",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda c, d: c.async_device_action(d, "resetDeviceFilter"),
    ),
    QcNanoButtonDescription(
        key="reset_cold_portions",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda c, d: c.async_reset_slider(d, "cold"),
    ),
    QcNanoButtonDescription(
        key="reset_hot_portions",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda c, d: c.async_reset_slider(d, "hot"),
    ),
    QcNanoButtonDescription(
        key="reset_ambient_portions",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda c, d: c.async_reset_slider(d, "ambient"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QcNanoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up buttons."""
    coordinator = entry.runtime_data
    async_add_entities(
        QcNanoButton(coordinator, device_id, description)
        for device_id in coordinator.data
        for description in BUTTONS
    )


class QcNanoButton(QcNanoEntity, ButtonEntity):
    """A QC nano button."""

    entity_description: QcNanoButtonDescription

    def __init__(self, coordinator, device_id: str, description: QcNanoButtonDescription) -> None:
        super().__init__(coordinator, device_id, description.key)
        self.entity_description = description
        self._attr_translation_key = description.key

    async def async_press(self) -> None:
        await self.entity_description.press_fn(self.coordinator, self._device_id)
