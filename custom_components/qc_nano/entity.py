"""Base entity for QC nano."""

from __future__ import annotations

from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import QcNanoCoordinator, QcNanoDevice


class QcNanoEntity(CoordinatorEntity[QcNanoCoordinator]):
    """Common base: one entity of one dispenser."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: QcNanoCoordinator, device_id: str, key: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_{key}"
        cloud = coordinator.data[device_id].cloud
        raw_mac = (cloud.get("macAddress") or "").replace("-", ":")
        mac = format_mac(raw_mac) if raw_mac else ""
        firmware = cloud.get("firmwareVersion") or {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            connections={(CONNECTION_NETWORK_MAC, mac)} if mac else set(),
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=cloud.get("name") or "QC nano",
            sw_version=firmware.get("version"),
            hw_version=cloud.get("hardwareVersion"),
            serial_number=cloud.get("serialNumber") or cloud.get("thingName"),
        )

    @property
    def device(self) -> QcNanoDevice:
        """The dispenser's current data."""
        return self.coordinator.data[self._device_id]

    @property
    def available(self) -> bool:
        return super().available and self._device_id in self.coordinator.data
