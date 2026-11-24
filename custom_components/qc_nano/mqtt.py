"""Minimal MQTT 3.1.1 client over AWS IoT WebSockets for QC nano live data.

Only what is needed is implemented: CONNECT, SUBSCRIBE (QoS 0),
incoming PUBLISH (QoS 0/1) and keepalive. This keeps the integration free of
extra dependencies and fully async on Home Assistant's aiohttp session.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import json
import logging
import struct
import time
from typing import Any
import uuid

import aiohttp

from .api import QcNanoError

_LOGGER = logging.getLogger(__name__)

KEEPALIVE = 60
RECONNECT_MIN = 5
RECONNECT_MAX = 300
# Reconnect a bit before the temporary AWS credentials expire.
CREDENTIAL_MARGIN = 300

MessageCallback = Callable[[str, dict[str, Any]], None]
UrlProvider = Callable[[], Awaitable[tuple[str, float]]]
ConnectCallback = Callable[[bool], None]


def _encode_str(value: str) -> bytes:
    raw = value.encode("utf-8")
    return struct.pack("!H", len(raw)) + raw


def _remaining_length(length: int) -> bytes:
    out = bytearray()
    while True:
        digit = length % 128
        length //= 128
        out.append(digit | 0x80 if length else digit)
        if not length:
            return bytes(out)


def _packet(first_byte: int, body: bytes) -> bytes:
    return bytes([first_byte]) + _remaining_length(len(body)) + body


def _split_packets(buffer: bytearray) -> list[tuple[int, bytes]]:
    """Pop complete MQTT packets from the buffer."""
    packets: list[tuple[int, bytes]] = []
    while len(buffer) >= 2:
        multiplier, length, pos = 1, 0, 1
        while True:
            if pos > 4:
                raise QcNanoError("Malformed MQTT packet length")
            if pos >= len(buffer):
                return packets
            byte = buffer[pos]
            length += (byte & 0x7F) * multiplier
            multiplier *= 128
            pos += 1
            if not byte & 0x80:
                break
        if len(buffer) < pos + length:
            return packets
        packets.append((buffer[0], bytes(buffer[pos : pos + length])))
        del buffer[: pos + length]
    return packets


class QcNanoMqtt:
    """Keeps an MQTT subscription to the account's QC nano topics alive."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        url_provider: UrlProvider,
        topics: list[str],
        on_message: MessageCallback,
        on_connection: ConnectCallback | None = None,
    ) -> None:
        self._session = session
        self._url_provider = url_provider
        self._topics = topics
        self._on_message = on_message
        self._on_connection = on_connection
        self._task: asyncio.Task | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self.connected = False
        self.last_message: float | None = None

    def start(self, create_task: Callable[..., asyncio.Task]) -> None:
        """Start the background connection loop."""
        if self._task is None:
            self._task = create_task(self._run(), "qc_nano_mqtt")

    async def stop(self) -> None:
        """Stop the connection loop."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._set_connected(False)

    def _set_connected(self, value: bool) -> None:
        if self.connected != value:
            self.connected = value
            if self._on_connection:
                self._on_connection(value)

    async def _run(self) -> None:
        delay = RECONNECT_MIN
        while True:
            started = time.monotonic()
            try:
                await self._session_once()
            except asyncio.CancelledError:
                raise
            except aiohttp.ClientResponseError as err:
                # never log the error text: it contains the presigned URL
                # with temporary AWS credentials
                _LOGGER.debug("Live connection rejected: HTTP %s", err.status)
            except (QcNanoError, aiohttp.ClientError, TimeoutError, OSError) as err:
                _LOGGER.debug("Live connection lost: %s", type(err).__name__)
            except Exception:  # noqa: BLE001 - never let the loop die
                _LOGGER.exception("Unexpected error in QC nano live connection")
            finally:
                self._set_connected(False)
            if time.monotonic() - started > 120:
                delay = RECONNECT_MIN
            _LOGGER.debug("Reconnecting live connection in %s s", delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_MAX)

    async def _session_once(self) -> None:
        url, expires = await self._url_provider()
        async with self._session.ws_connect(
            url, protocols=("mqtt",), heartbeat=None, timeout=aiohttp.ClientWSTimeout(ws_close=10)
        ) as ws:
            self._ws = ws
            client_id = f"ha-qc-nano-{uuid.uuid4()}"
            connect = (
                _encode_str("MQTT")
                + bytes([4, 0x02])  # protocol level 4, clean session
                + struct.pack("!H", KEEPALIVE)
                + _encode_str(client_id)
            )
            await ws.send_bytes(_packet(0x10, connect))
            buffer = bytearray()
            packet_id = 1
            connack = False
            deadline = time.time() + max(expires - time.time() - CREDENTIAL_MARGIN, 60)
            last_ping = time.monotonic()
            last_packet = time.monotonic()

            while True:
                if time.time() > deadline:
                    _LOGGER.debug("Credentials about to expire, reconnecting")
                    return
                try:
                    msg = await ws.receive(timeout=KEEPALIVE / 2)
                except TimeoutError:
                    msg = None
                if time.monotonic() - last_packet > KEEPALIVE * 1.5:
                    raise QcNanoError("No response from the broker (half-open connection)")
                if time.monotonic() - last_ping >= KEEPALIVE / 2:
                    await ws.send_bytes(b"\xc0\x00")  # PINGREQ
                    last_ping = time.monotonic()
                if msg is None:
                    continue
                if msg.type in (
                    aiohttp.WSMsgType.CLOSE,
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.CLOSING,
                    aiohttp.WSMsgType.ERROR,
                ):
                    raise QcNanoError(f"WebSocket closed: {msg.type} {msg.data}")
                if msg.type != aiohttp.WSMsgType.BINARY:
                    continue
                buffer.extend(msg.data)
                last_packet = time.monotonic()
                for first, body in _split_packets(buffer):
                    ptype = first >> 4
                    if ptype == 2:  # CONNACK
                        if len(body) < 2 or body[1] != 0:
                            raise QcNanoError(f"MQTT connection refused: {body.hex()}")
                        connack = True
                        for topic in self._topics:
                            sub = struct.pack("!H", packet_id) + _encode_str(topic) + b"\x00"
                            packet_id += 1
                            await ws.send_bytes(_packet(0x82, sub))
                    elif ptype == 9:  # SUBACK
                        if body[2:] and body[2] == 0x80:
                            raise QcNanoError("MQTT subscription rejected")
                        self._set_connected(True)
                    elif ptype == 3 and connack:  # PUBLISH
                        await self._handle_publish(ws, first, body)
                    elif ptype == 13:  # PINGRESP
                        pass

    async def _handle_publish(
        self, ws: aiohttp.ClientWebSocketResponse, first: int, body: bytes
    ) -> None:
        qos = (first >> 1) & 0x03
        topic_len = struct.unpack("!H", body[:2])[0]
        topic = body[2 : 2 + topic_len].decode("utf-8", errors="replace")
        pos = 2 + topic_len
        if qos:
            pid = body[pos : pos + 2]
            pos += 2
            await ws.send_bytes(b"\x40\x02" + pid)  # PUBACK
        try:
            payload = json.loads(body[pos:].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            _LOGGER.debug("Ignoring non-JSON message on %s", topic)
            return
        if not isinstance(payload, dict):
            return
        self.last_message = time.time()
        try:
            self._on_message(topic, payload)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Error handling live message on %s", topic)
