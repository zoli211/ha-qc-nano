"""Constants for the QC nano integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "qc_nano"
MANUFACTURER: Final = "Q&C"
MODEL: Final = "nano"

# Public client configuration of the official app (not secrets: these are
# shipped in every copy of the mobile app and identify the app, not a user).
REGION: Final = "eu-west-2"
COGNITO_USER_POOL_ID: Final = "eu-west-2_No4OepeHO"
COGNITO_CLIENT_ID: Final = "5m77ktsji2ovjjbjihk8st1u72"
COGNITO_IDENTITY_POOL_ID: Final = "eu-west-2:47f3dcb5-a8bf-45eb-bef8-cca5ba370fba"
COGNITO_ENDPOINT: Final = f"https://cognito-idp.{REGION}.amazonaws.com/"
COGNITO_IDENTITY_ENDPOINT: Final = f"https://cognito-identity.{REGION}.amazonaws.com/"
COGNITO_LOGIN_PROVIDER: Final = (
    f"cognito-idp.{REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}"
)
APPSYNC_URL: Final = (
    "https://opxic66jzfeupcxnryv3qlmvym.appsync-api.eu-west-2.amazonaws.com/graphql"
)
IOT_HOST: Final = "a28jj2y567rw84-ats.iot.eu-west-2.amazonaws.com"
IOT_TOPIC_PREFIX: Final = "production-qc"

CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_LIVE_INTERVAL: Final = "live_interval"
CONF_LIVE_ENABLED: Final = "live_enabled"

DEFAULT_SCAN_INTERVAL: Final = 300  # seconds, cloud (GraphQL) polling
DEFAULT_LIVE_INTERVAL: Final = 300  # seconds; one request streams for 9+ minutes
MIN_SCAN_INTERVAL: Final = 30
MIN_LIVE_INTERVAL: Final = 60

SLIDER_LEVELS: Final = ("tiny", "small", "normal", "large", "mega")

# kind -> (settings key in the device query, UpdateDeviceSettingsInput key)
SLIDERS: Final = {
    "cold": ("coldQuantitySlider", "coldSlider"),
    "hot": ("hotQuantitySlider", "hotSlider"),
    "ambient": ("ambientQuantitySlider", "ambientSlider"),
}

COLD_TEMP_MIN: Final = 4
COLD_TEMP_MAX: Final = 16

COOLING_MODES: Final = ("off", "standard", "boost")

WEEKDAYS: Final = ("mo", "tu", "we", "th", "fr", "sa", "su")
