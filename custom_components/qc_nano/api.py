"""Async client for the QC nano cloud (AWS Cognito + AppSync GraphQL)."""

from __future__ import annotations

import asyncio
import base64
from datetime import UTC, datetime
import hashlib
import hmac
import json
import logging
import time
from typing import Any
from urllib.parse import quote

import aiohttp

from .const import (
    APPSYNC_URL,
    COGNITO_CLIENT_ID,
    COGNITO_ENDPOINT,
    COGNITO_IDENTITY_ENDPOINT,
    COGNITO_IDENTITY_POOL_ID,
    COGNITO_LOGIN_PROVIDER,
    IOT_HOST,
    REGION,
    SLIDER_LEVELS,
)

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)

DEVICE_FIELDS = """
  id
  name
  thingName
  macAddress
  timezone
  serialNumber
  hardwareVersion
  connection
  status
  disconnectedAt
  activatedAt
  createdAt
  coldWaterTemp
  usedVolume
  systemHealth
  cleaningStatus
  nextCleaning
  lastFilterClean
  lastFilterChange
  isNewServer
  forceOTA
  shouldReinstall
  summary { ambientWater coldWater hotWater }
  filter {
    serialNumber
    usedVolume
    maxVolume
    hygiene
    filterLife
    usedInMonths
    status
    dateOfUsed
    nextFilterChange
    nextCleaning
    firstOperationDate
  }
  firmwareVersion { id version esp stm createdAt }
  otaSession { id status progress createdAt }
  settings {
    name
    coldTemperature
    cooling
    childLock
    lightOff
    energySaver
    energySaverStatus
    volumeSliderStatus
    coldQuantitySlider { ...SliderFields }
    hotQuantitySlider { ...SliderFields }
    ambientQuantitySlider { ...SliderFields }
  }
"""

SLIDER_FRAGMENT = """
fragment SliderFields on Slider {
  tiny { value status }
  small { value status }
  normal { value status }
  large { value status }
  mega { value status }
}
"""

QUERY_DEVICES = """
query devices($limit: Int) {
  devices(limit: $limit) {
    devices { id name thingName macAddress hardwareVersion }
  }
}
"""

QUERY_DEVICE = (
    "query device($deviceId: ID!) {\n  device(deviceId: $deviceId) {"
    + DEVICE_FIELDS
    + "  }\n}\n"
    + SLIDER_FRAGMENT
)

QUERY_TODAY = """
query today($params: StatConsumptionsInput!) {
  statConsumptions(params: $params) {
    isSuccess
    message
    coldWater
    hotWater
    ambientWater
  }
}
"""

QUERY_LATEST_FIRMWARE = """
query latestFirmware($hardwareVersion: String!) {
  getLatestFirmware(hardwareVersion: $hardwareVersion) {
    id version esp stm hardwareVersion createdAt
  }
}
"""

MUTATION_UPDATE_SETTINGS = """
mutation updateDeviceSettings($params: UpdateDeviceSettingsInput!) {
  updateDeviceSettings(params: $params) { isSuccess message }
}
"""

MUTATION_RESET_SLIDER = """
mutation resetVolumeSlider($params: ResetVolumeSliderInput!) {
  resetVolumeSlider(params: $params) { isSuccess message }
}
"""

SIMPLE_DEVICE_MUTATIONS = {
    "requestDeviceInfo",
    "requestConsumption",
    "requestLiveMeasurement",
    "resetDeviceFilter",
    "upgradeFirmware",
}


class QcNanoError(Exception):
    """Generic QC nano cloud error."""


class QcNanoAuthError(QcNanoError):
    """Login failed or the session can no longer be refreshed."""


class QcNanoConnectionError(QcNanoError):
    """The cloud could not be reached."""


def _jwt_payload(token: str) -> dict[str, Any]:
    try:
        part = token.split(".")[1]
        part += "=" * (-len(part) % 4)
        return json.loads(base64.urlsafe_b64decode(part.encode("ascii")))
    except (IndexError, ValueError) as err:
        raise QcNanoAuthError("Invalid token received") from err


class QcNanoApi:
    """Minimal QC nano cloud client."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
    ) -> None:
        self._session = session
        self._username = username.strip().lower()
        self._password = password
        self._id_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float = 0
        self._lock = asyncio.Lock()
        self._identity_id: str | None = None
        self._iot_policy_attached = False
        self.user_id: str | None = None

    # ------------------------------------------------------------------ auth

    async def _cognito(self, flow: str, params: dict[str, str]) -> dict[str, Any]:
        headers = {
            "Content-Type": "application/x-amz-json-1.1",
            "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
        }
        payload = {
            "AuthFlow": flow,
            "ClientId": COGNITO_CLIENT_ID,
            "AuthParameters": params,
        }
        try:
            async with self._session.post(
                COGNITO_ENDPOINT,
                data=json.dumps(payload),
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                body = await resp.json(content_type=None)
                status = resp.status
        except (aiohttp.ClientError, TimeoutError) as err:
            raise QcNanoConnectionError(f"Cognito unreachable: {err}") from err

        if status >= 400:
            code = str(body.get("__type", "")) if isinstance(body, dict) else ""
            message = body.get("message", "") if isinstance(body, dict) else body
            if code.endswith(
                (
                    "NotAuthorizedException",
                    "UserNotFoundException",
                    "UserNotConfirmedException",
                    "PasswordResetRequiredException",
                )
            ):
                raise QcNanoAuthError(f"{code}: {message}")
            raise QcNanoError(f"Cognito HTTP {status}: {code} {message}")

        if body.get("ChallengeName"):
            raise QcNanoAuthError(
                f"Unsupported login challenge: {body['ChallengeName']}"
            )
        result = body.get("AuthenticationResult")
        if not result:
            raise QcNanoAuthError("Cognito did not return tokens")
        return result

    def _store_tokens(self, result: dict[str, Any]) -> None:
        self._id_token = result["IdToken"]
        if result.get("RefreshToken"):
            self._refresh_token = result["RefreshToken"]
        self._expires_at = time.time() + int(result.get("ExpiresIn", 3600))
        self.user_id = _jwt_payload(self._id_token).get("sub")

    async def async_login(self) -> str:
        """Log in with username and password; return the Cognito user id."""
        result = await self._cognito(
            "USER_PASSWORD_AUTH",
            {"USERNAME": self._username, "PASSWORD": self._password},
        )
        self._store_tokens(result)
        if not self.user_id:
            raise QcNanoAuthError("Token has no user id")
        return self.user_id

    async def _async_ensure_token(self) -> str:
        async with self._lock:
            if self._id_token and self._expires_at - 120 > time.time():
                return self._id_token
            if self._refresh_token:
                try:
                    result = await self._cognito(
                        "REFRESH_TOKEN_AUTH", {"REFRESH_TOKEN": self._refresh_token}
                    )
                    self._store_tokens(result)
                    return self._id_token  # type: ignore[return-value]
                except QcNanoAuthError:
                    _LOGGER.debug("Refresh token rejected, logging in again")
                    self._refresh_token = None
            await self.async_login()
            return self._id_token  # type: ignore[return-value]

    # ------------------------------------------------------------------- iot

    async def _cognito_identity(self, target: str, body: dict[str, Any]) -> dict:
        headers = {
            "Content-Type": "application/x-amz-json-1.1",
            "X-Amz-Target": f"AWSCognitoIdentityService.{target}",
        }
        try:
            async with self._session.post(
                COGNITO_IDENTITY_ENDPOINT,
                data=json.dumps(body),
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                status = resp.status
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise QcNanoConnectionError(f"Cognito Identity unreachable: {err}") from err
        if status >= 400:
            raise QcNanoError(f"Cognito Identity HTTP {status}: {data}")
        return data

    async def async_get_iot_url(self) -> tuple[str, float]:
        """Return a presigned AWS IoT MQTT-over-WebSocket URL and its expiry.

        Uses the account's own Cognito identity (the same way the mobile app
        subscribes to live data); no device certificate is involved.
        """
        token = await self._async_ensure_token()
        logins = {COGNITO_LOGIN_PROVIDER: token}
        if not self._identity_id:
            data = await self._cognito_identity(
                "GetId", {"IdentityPoolId": COGNITO_IDENTITY_POOL_ID, "Logins": logins}
            )
            self._identity_id = data["IdentityId"]
        if not self._iot_policy_attached:
            data = await self._graphql(
                "mutation attachIoTPolicy($identityId: String!) { "
                "attachIoTPolicy(identityId: $identityId) { isSuccess message } }",
                {"identityId": self._identity_id},
            )
            _check_response(data.get("attachIoTPolicy"), "attachIoTPolicy")
            self._iot_policy_attached = True
        data = await self._cognito_identity(
            "GetCredentialsForIdentity",
            {"IdentityId": self._identity_id, "Logins": logins},
        )
        creds = data["Credentials"]
        expires = float(creds.get("Expiration") or time.time() + 3600)
        url = _presign_iot_url(
            creds["AccessKeyId"], creds["SecretKey"], creds["SessionToken"]
        )
        return url, expires

    # --------------------------------------------------------------- graphql

    async def _graphql(
        self, query: str, variables: dict[str, Any] | None = None, retry: bool = True
    ) -> dict[str, Any]:
        token = await self._async_ensure_token()
        try:
            async with self._session.post(
                APPSYNC_URL,
                json={"query": query, "variables": variables or {}},
                headers={"Authorization": token},
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                status = resp.status
                body = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise QcNanoConnectionError(f"AppSync unreachable: {err}") from err

        if status in (401, 403) or _is_unauthorized(body):
            if retry:
                self._expires_at = 0
                return await self._graphql(query, variables, retry=False)
            raise QcNanoAuthError("AppSync rejected the session")
        if status >= 400:
            raise QcNanoError(f"AppSync HTTP {status}: {body}")
        if body.get("errors"):
            messages = "; ".join(e.get("message", "?") for e in body["errors"])
            if body.get("data") is None:
                raise QcNanoError(f"GraphQL error: {messages}")
            _LOGGER.debug("GraphQL partial error: %s", messages)
        return body.get("data") or {}

    async def async_get_devices(self) -> list[dict[str, Any]]:
        """Return the devices bound to the account."""
        data = await self._graphql(QUERY_DEVICES, {"limit": 50})
        return [d for d in (data.get("devices") or {}).get("devices") or [] if d]

    async def async_get_device(self, device_id: str) -> dict[str, Any] | None:
        """Return the full state of one device."""
        data = await self._graphql(QUERY_DEVICE, {"deviceId": device_id})
        return data.get("device")

    async def async_get_today(self, device_id: str, day: str) -> dict[str, Any]:
        """Return the consumption of a single day (YYYY-MM-DD, device local)."""
        data = await self._graphql(
            QUERY_TODAY, {"params": {"deviceId": device_id, "start": day, "stop": day}}
        )
        return data.get("statConsumptions") or {}

    async def async_get_latest_firmware(
        self, hardware_version: str
    ) -> dict[str, Any] | None:
        """Return the latest firmware offered for a hardware version."""
        data = await self._graphql(
            QUERY_LATEST_FIRMWARE, {"hardwareVersion": hardware_version}
        )
        return data.get("getLatestFirmware")

    async def async_update_settings(self, device_id: str, **params: Any) -> None:
        """Call updateDeviceSettings with the given fields."""
        payload = {"deviceId": device_id, **params}
        data = await self._graphql(MUTATION_UPDATE_SETTINGS, {"params": payload})
        _check_response(data.get("updateDeviceSettings"), "updateDeviceSettings")

    async def async_set_slider(
        self, device_id: str, param: str, slider: dict[str, dict[str, Any]]
    ) -> None:
        """Write a full quantity slider (all five levels) as AWSJSON."""
        missing = [
            level
            for level in SLIDER_LEVELS
            if (slider.get(level) or {}).get("value") is None
            or (slider.get(level) or {}).get("status") is None
        ]
        if missing:
            raise QcNanoError(f"Incomplete slider, missing: {', '.join(missing)}")
        value = {
            level: {
                "value": int(slider[level]["value"]),
                "status": bool(slider[level]["status"]),
            }
            for level in SLIDER_LEVELS
        }
        await self.async_update_settings(device_id, **{param: json.dumps(value)})

    async def async_reset_slider(self, device_id: str, which: str) -> None:
        """Reset one quantity slider (hotSlider/coldSlider/ambientSlider)."""
        params = {
            "deviceId": device_id,
            "hotSlider": which == "hotSlider",
            "coldSlider": which == "coldSlider",
            "ambientSlider": which == "ambientSlider",
        }
        data = await self._graphql(MUTATION_RESET_SLIDER, {"params": params})
        _check_response(data.get("resetVolumeSlider"), "resetVolumeSlider")

    async def async_device_mutation(self, name: str, device_id: str) -> None:
        """Run one of the simple `mutation x(deviceId)` calls."""
        if name not in SIMPLE_DEVICE_MUTATIONS:
            raise ValueError(name)
        query = (
            f"mutation {name}($deviceId: ID!) {{ "
            f"{name}(deviceId: $deviceId) {{ isSuccess message }} }}"
        )
        data = await self._graphql(query, {"deviceId": device_id})
        _check_response(data.get(name), name)


def _presign_iot_url(access_key: str, secret_key: str, session_token: str) -> str:
    """SigV4-presign the AWS IoT MQTT WebSocket endpoint."""
    now = datetime.now(UTC)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    day = now.strftime("%Y%m%d")
    service = "iotdevicegateway"
    scope = f"{day}/{REGION}/{service}/aws4_request"
    query = {
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
        "X-Amz-Credential": f"{access_key}/{scope}",
        "X-Amz-Date": amz_date,
        "X-Amz-SignedHeaders": "host",
    }
    canonical_query = "&".join(
        f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in sorted(query.items())
    )
    canonical_request = "\n".join(
        [
            "GET",
            "/mqtt",
            canonical_query,
            f"host:{IOT_HOST}",
            "",
            "host",
            hashlib.sha256(b"").hexdigest(),
        ]
    )
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            scope,
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        ]
    )
    key = f"AWS4{secret_key}".encode()
    for part in (day, REGION, service, "aws4_request"):
        key = hmac.new(key, part.encode(), hashlib.sha256).digest()
    signature = hmac.new(key, string_to_sign.encode(), hashlib.sha256).hexdigest()
    # AWS IoT expects the session token to be appended after signing.
    return (
        f"wss://{IOT_HOST}/mqtt?{canonical_query}&X-Amz-Signature={signature}"
        f"&X-Amz-Security-Token={quote(session_token, safe='')}"
    )


def _is_unauthorized(body: Any) -> bool:
    if not isinstance(body, dict):
        return False
    for err in body.get("errors") or []:
        etype = str(err.get("errorType", ""))
        if etype in ("UnauthorizedException", "Unauthorized"):
            return True
    return False


def _check_response(result: dict[str, Any] | None, name: str) -> None:
    if not result or not result.get("isSuccess"):
        message = (result or {}).get("message") or "no success flag"
        raise QcNanoError(f"{name} failed: {message}")
