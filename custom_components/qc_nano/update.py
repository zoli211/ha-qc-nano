"""Firmware update entity for QC nano."""

from __future__ import annotations

from typing import Any

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import QcNanoConfigEntry
from .entity import QcNanoEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QcNanoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the firmware update entity."""
    coordinator = entry.runtime_data
    async_add_entities(QcNanoFirmware(coordinator, d) for d in coordinator.data)


class QcNanoFirmware(QcNanoEntity, UpdateEntity):
    """Firmware of the dispenser, upgradable over the cloud."""

    _attr_translation_key = "firmware"
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS

    def __init__(self, coordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "firmware")

    @property
    def installed_version(self) -> str | None:
        return (self.device.cloud.get("firmwareVersion") or {}).get("version")

    @property
    def latest_version(self) -> str | None:
        latest = self.device.latest_firmware or {}
        return latest.get("version") or self.installed_version

    @property
    def in_progress(self) -> bool:
        ota = self.device.cloud.get("otaSession") or {}
        status = str(ota.get("status") or "").lower()
        return bool(ota) and status not in ("", "done", "success", "completed", "failed", "error")

    @property
    def update_percentage(self) -> int | None:
        if not self.in_progress:
            return None
        progress = (self.device.cloud.get("otaSession") or {}).get("progress")
        try:
            return int(float(progress))
        except (TypeError, ValueError):
            return None

    async def async_install(self, version: str | None, backup: bool, **kwargs: Any) -> None:
        await self.coordinator.async_device_action(self._device_id, "upgradeFirmware")
