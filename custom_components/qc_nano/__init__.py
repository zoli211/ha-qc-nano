"""The QC nano water dispenser integration."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .api import QcNanoApi, QcNanoAuthError, QcNanoError
from .const import DOMAIN
from .coordinator import QcNanoConfigEntry, QcNanoCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

CARD_URL = "/qc_nano/qc-nano-card.js"
CARD_PATH = Path(__file__).parent / "frontend" / "qc-nano-card.js"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
    Platform.UPDATE,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the dashboard card and load it on every dashboard."""
    integration = await async_get_integration(hass, DOMAIN)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_PATH), True)]
    )
    # the version in the query string busts the browser cache after updates
    add_extra_js_url(hass, f"{CARD_URL}?v={integration.version}")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: QcNanoConfigEntry) -> bool:
    """Set up QC nano from a config entry."""
    api = QcNanoApi(
        async_get_clientsession(hass),
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    try:
        await api.async_login()
    except QcNanoAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except QcNanoError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = QcNanoCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_start_live()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: QcNanoConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_shutdown()
    return unloaded
