"""Data coordinator for QC nano: cloud polling plus live MQTT data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import time
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import QcNanoApi, QcNanoAuthError, QcNanoError
from .const import (
    CONF_LIVE_ENABLED,
    CONF_LIVE_INTERVAL,
    CONF_SCAN_INTERVAL,
    DEFAULT_LIVE_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    IOT_TOPIC_PREFIX,
    SLIDERS,
)
from .mqtt import QcNanoMqtt

_LOGGER = logging.getLogger(__name__)

type QcNanoConfigEntry = ConfigEntry[QcNanoCoordinator]

FIRMWARE_CHECK_INTERVAL = 6 * 3600


@dataclass
class QcNanoDevice:
    """Everything known about one dispenser."""

    device_id: str
    thing_name: str | None = None
    cloud: dict[str, Any] = field(default_factory=dict)
    today: dict[str, Any] = field(default_factory=dict)
    latest_firmware: dict[str, Any] | None = None
    live: dict[str, Any] = field(default_factory=dict)
    info: dict[str, Any] = field(default_factory=dict)
    filter_info: dict[str, Any] = field(default_factory=dict)
    live_updated: datetime | None = None
    info_updated: datetime | None = None

    @property
    def settings(self) -> dict[str, Any]:
        return self.cloud.get("settings") or {}

    @property
    def connected(self) -> bool:
        return self.cloud.get("connection") == "CONNECTED"


class QcNanoCoordinator(DataUpdateCoordinator[dict[str, QcNanoDevice]]):
    """Polls the QC cloud and merges in live data pushed over MQTT."""

    config_entry: QcNanoConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: QcNanoConfigEntry, api: QcNanoApi
    ) -> None:
        scan = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan),
        )
        self.api = api
        self.data = {}
        self.mqtt: QcNanoMqtt | None = None
        self._firmware_checked: float = 0
        self._unsub_live: CALLBACK_TYPE | None = None
        self._refresh_later: CALLBACK_TYPE | None = None

    # ------------------------------------------------------------- polling

    async def _async_update_data(self) -> dict[str, QcNanoDevice]:
        try:
            devices = await self.api.async_get_devices()
            result: dict[str, QcNanoDevice] = {}
            check_firmware = time.monotonic() - self._firmware_checked > (
                FIRMWARE_CHECK_INTERVAL
            ) or not self._firmware_checked
            for summary in devices:
                device_id = str(summary["id"])
                current = (self.data or {}).get(device_id) or QcNanoDevice(device_id)
                cloud = await self.api.async_get_device(device_id)
                if not cloud:
                    continue
                current.cloud = {**summary, **cloud}
                current.thing_name = summary.get("thingName") or current.thing_name
                day = _local_day(cloud.get("timezone"))
                try:
                    current.today = await self.api.async_get_today(device_id, day)
                except QcNanoError as err:
                    _LOGGER.debug("Could not read today's consumption: %s", err)
                hw = cloud.get("hardwareVersion")
                if check_firmware and hw:
                    try:
                        current.latest_firmware = (
                            await self.api.async_get_latest_firmware(hw)
                        )
                    except QcNanoError as err:
                        _LOGGER.debug("Could not read latest firmware: %s", err)
                result[device_id] = current
            if check_firmware:
                self._firmware_checked = time.monotonic()
            if self.data and set(result) != set(self.data):
                _LOGGER.info("QC nano device list changed, reloading")
                self.hass.config_entries.async_schedule_reload(
                    self.config_entry.entry_id
                )
        except QcNanoAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except QcNanoError as err:
            raise UpdateFailed(str(err)) from err
        return result

    # ---------------------------------------------------------------- live

    async def async_start_live(self) -> None:
        """Connect to live data and periodically ask devices to stream."""
        if not self.config_entry.options.get(CONF_LIVE_ENABLED, True):
            return
        user_id = self.api.user_id
        if not user_id:
            return
        self.mqtt = QcNanoMqtt(
            async_get_clientsession(self.hass),
            self.api.async_get_iot_url,
            [f"{IOT_TOPIC_PREFIX}/{user_id}/#"],
            self._handle_message,
            self._handle_live_connection,
        )
        self.mqtt.start(
            lambda coro, name: self.config_entry.async_create_background_task(
                self.hass, coro, name
            )
        )
        interval = self.config_entry.options.get(
            CONF_LIVE_INTERVAL, DEFAULT_LIVE_INTERVAL
        )
        self._unsub_live = async_track_time_interval(
            self.hass, self._async_request_live, timedelta(seconds=interval)
        )

    async def async_shutdown(self) -> None:
        """Stop timers and the live connection."""
        if self._unsub_live:
            self._unsub_live()
            self._unsub_live = None
        if self._refresh_later:
            self._refresh_later()
            self._refresh_later = None
        if self.mqtt:
            await self.mqtt.stop()
            self.mqtt = None
        await super().async_shutdown()

    @callback
    def _handle_live_connection(self, connected: bool) -> None:
        _LOGGER.debug("Live connection %s", "up" if connected else "down")
        if connected:
            self.config_entry.async_create_task(
                self.hass, self._async_request_live(), "qc_nano_request_live"
            )
        self.async_update_listeners()

    async def _async_request_live(self, _now: datetime | None = None) -> None:
        if not self.mqtt or not self.mqtt.connected:
            return
        for device in list((self.data or {}).values()):
            if not device.connected:
                continue
            for name in ("requestLiveMeasurement", "requestDeviceInfo"):
                try:
                    await self.api.async_device_mutation(name, device.device_id)
                except QcNanoError as err:
                    _LOGGER.debug("%s failed: %s", name, err)

    @callback
    def _handle_message(self, topic: str, payload: dict[str, Any]) -> None:
        parts = topic.split("/")
        if parts[-1] == "notify":
            # device connection changes, OTA progress, a device added on
            # another phone (account level topic) ...
            self._schedule_delayed_refresh(2)
            return
        if len(parts) < 4:
            return
        thing, kind = parts[2], parts[-1]
        device = next(
            (d for d in (self.data or {}).values() if d.thing_name == thing), None
        )
        if device is None:
            return
        value = payload.get("value")
        now = dt_util.utcnow()
        if kind == "live_measurement" and isinstance(value, dict):
            device.live = value
            device.live_updated = now
        elif kind == "nano_info" and isinstance(value, dict):
            device.info = value
            device.info_updated = now
        elif kind == "filter_info" and isinstance(value, dict):
            device.filter_info = value
        else:
            return
        self.async_update_listeners()

    # ------------------------------------------------------------- actions

    @callback
    def _schedule_delayed_refresh(self, delay: float) -> None:
        if self._refresh_later:
            self._refresh_later()

        @callback
        def _do_refresh(_now: datetime) -> None:
            self._refresh_later = None
            self.config_entry.async_create_task(
                self.hass, self.async_request_refresh(), "qc_nano_refresh"
            )

        self._refresh_later = async_call_later(self.hass, delay, _do_refresh)

    async def async_update_settings(
        self, device_id: str, local: dict[str, Any] | None = None, **params: Any
    ) -> None:
        """Write settings, update local state optimistically, then re-read."""
        try:
            await self.api.async_update_settings(device_id, **params)
        except QcNanoError as err:
            raise HomeAssistantError(f"QC nano: {err}") from err
        device = self.data.get(device_id)
        if device and local:
            device.cloud.setdefault("settings", {}).update(local)
            self.async_update_listeners()
        self._schedule_delayed_refresh(5)

    async def async_set_slider_level(
        self, device_id: str, kind: str, level: str, **changes: Any
    ) -> None:
        """Change value/status of one level of a quantity slider."""
        settings_key, param = SLIDERS[kind]
        device = self.data.get(device_id)
        if device is None:
            raise HomeAssistantError("QC nano: device is no longer available")
        slider = {
            k: dict(v or {}) for k, v in (device.settings.get(settings_key) or {}).items()
        }
        slider.setdefault(level, {}).update(changes)
        try:
            await self.api.async_set_slider(device_id, param, slider)
        except QcNanoError as err:
            raise HomeAssistantError(f"QC nano: {err}") from err
        device.cloud.setdefault("settings", {})[settings_key] = slider
        self.async_update_listeners()
        self._schedule_delayed_refresh(5)

    async def async_reset_slider(self, device_id: str, kind: str) -> None:
        """Reset a quantity slider to factory values."""
        try:
            await self.api.async_reset_slider(device_id, SLIDERS[kind][1])
        except QcNanoError as err:
            raise HomeAssistantError(f"QC nano: {err}") from err
        self._schedule_delayed_refresh(5)

    async def async_device_action(self, device_id: str, name: str) -> None:
        """Run a simple device mutation and refresh."""
        try:
            await self.api.async_device_mutation(name, device_id)
        except QcNanoError as err:
            raise HomeAssistantError(f"QC nano: {err}") from err
        self._schedule_delayed_refresh(5)

    async def async_refresh_now(self, device_id: str) -> None:
        """Ask the device for fresh data and re-read the cloud."""
        for name in ("requestDeviceInfo", "requestConsumption", "requestLiveMeasurement"):
            try:
                await self.api.async_device_mutation(name, device_id)
            except QcNanoError as err:
                _LOGGER.debug("%s failed: %s", name, err)
        self._schedule_delayed_refresh(3)


def _local_day(timezone: str | None) -> str:
    try:
        tz = ZoneInfo(timezone) if timezone else dt_util.get_default_time_zone()
    except (KeyError, ValueError):
        tz = dt_util.get_default_time_zone()
    return datetime.now(tz).strftime("%Y-%m-%d")
