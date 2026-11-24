"""Diagnostics for QC nano."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import QcNanoConfigEntry

TO_REDACT = {
    CONF_PASSWORD,
    CONF_USERNAME,
    "macAddress",
    "thingName",
    "thing_name",
    "serialNumber",
    "serial_number",
    "device_id",
    "id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: QcNanoConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "live_connected": bool(coordinator.mqtt and coordinator.mqtt.connected),
        "devices": [
            async_redact_data(asdict(device), TO_REDACT)
            for device in coordinator.data.values()
        ],
    }
