# QC nano for Home Assistant

[![Open your Home Assistant instance and open this repository in the Marketplace.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=zoli211&repository=ha-qc-nano&category=Integration)
[![Open your Home Assistant instance and start setting up QC nano.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=qc_nano)

Unofficial Home Assistant integration for the Q&C **nano** water dispenser.
It uses the same cloud as the official Q&C app: your own QC account, no
extra hardware, no device certificates.

- Sign in from the Home Assistant UI with the e-mail address and password of
  your QC account.
- Every setting of the app is available as an entity.
- Live data (temperatures, valves, cooling and heating unit, fan) is pushed in
  real time over the cloud's MQTT channel, the same way the app receives it.
- Settings, consumption, filter and cleaning data are polled from the cloud.

This project is not affiliated with or endorsed by Q&C.

## Requirements

- The dispenser must already be set up and connected to the cloud (with the
  official app or any other provisioning tool). This integration does not do
  Bluetooth or WiFi provisioning.
- Home Assistant 2026.3 or newer (tested on 2026.11).

## Installation

### Marketplace / HACS (custom repository)

Use the first button above, or add the repository by hand:

1. Home Assistant 2026.11 and newer: **Settings → Marketplace**. Older
   versions: **HACS**. Open the menu and choose **Custom repositories**.
2. Add `https://github.com/zoli211/ha-qc-nano` with the type **Integration**.
3. Install **QC nano** and restart Home Assistant.

### Manual

Copy `custom_components/qc_nano` into the `custom_components` folder of your
Home Assistant configuration and restart Home Assistant.

## Setup

**Settings → Devices & services → Add integration → QC nano**, then enter the
e-mail address and password of your QC account. Every dispenser bound to the
account is added as a device.

If the password changes, Home Assistant asks you to sign in again
(re-authentication). The account can also be changed with **Reconfigure**.

### Options

- **Cloud polling interval** (default 300 s): how often settings,
  consumption and filter data are read.
- **Live data** (default on): real-time data over MQTT.
- **Live data request interval** (default 300 s): how often the dispenser
  is asked to stream live measurements. One request keeps it streaming for
  roughly ten minutes.

## Entities

### Sensors

- Cold water temperature, hot water temperature, board temperature
- Water today (total, cold, hot, room temperature)
- Total water dispensed (total, cold, hot, room temperature)
- Water since the last filter change (cold, hot, room temperature)
- Filter: used volume, capacity, remaining capacity, status, next change,
  last change, lifetime, months used, first use
- Cleaning: status, next cleaning, last cleaning
- System health (same rule as the app: worst of filter and cleaning status)
- Diagnostics: fan speed and power, operating hours (total, cooling unit,
  heating unit), valve opening counts, WiFi signal, hygiene counter, last
  disconnect, last live update

The cold water temperature is the value the dispenser itself reports (the
official app shows the same number). On some units this sensor does not
follow the actual water temperature, so check it against the real water
before building automations on it.

Volume sensors use the `water` device class, so they can be added to the
Energy dashboard's water consumption.

### Binary sensors

- Cloud connection, live data connection
- Power, cooling, heating
- Cold, hot and room temperature valve open
- Filter needs attention, cleaning needed

### Controls

- Cooling mode (select): off, standard, boost
- Cold water target temperature (number): 4–16 °C
- Switches: child lock, lights off, energy saver, portion buttons
- Portions: for each tap (cold, hot, room temperature) and each size (tiny,
  small, normal, large, mega) a volume in mL and an enable switch
- Energy saver active hours, one text entity per weekday. Use hour ranges
  such as `6-24` or `6-12,14-22`, or `off` to disable the day.
- Buttons: refresh from device, confirm filter replacement, reset portions
  (per tap)
- Firmware update entity (install a new firmware over the cloud)

**Confirm filter replacement** resets the filter counter in the cloud, just
like the app does after a filter change. Only press it after you actually
replaced the filter.

## Dashboard card

The integration ships its own dashboard card and loads it automatically, no
extra resource is needed. Add it to a dashboard:

```yaml
type: custom:qc-nano-card
```

- A schematic drawing of the dispenser with the HOT / ROOM / COLD buttons:
  the water stream and the button light up while a tap is open, the
  snowflake pulses while the cooling unit runs, a lock shows the child lock.
- Today's consumption, the remaining filter capacity with the next change,
  and the cooling mode with the target temperature.
- Warnings for a due filter change, needed cleaning or a lost connection.
- Tap the card for the details: cooling mode, target temperature, child
  lock, lights, energy saver, portion buttons, and every portion size per tap
  (largest first) with − / + buttons and an enable toggle. Changes are sent
  after you stop pressing, so a long press is a single cloud call.

Options:

- `device_id`: only needed when the account has more than one dispenser.
- `title`: header text.
- `embedded: true`: no own card frame and header, for dashboards that wrap
  cards in their own panels.

The card is keyboard and screen reader friendly (the details open as a modal
dialog, Escape closes it) and follows the Home Assistant theme. Entity ids are
not hard coded, so it works in any language.

## How it works

- Login: AWS Cognito user pool (`USER_PASSWORD_AUTH`), the same app client
  the official app uses.
- State and settings: AWS AppSync GraphQL (`device`, `devices`,
  `statConsumptions`, `updateDeviceSettings`, `resetVolumeSlider`, ...).
  The schema can be inspected with GraphQL introspection.
- Live data: a Cognito identity for your account, MQTT over WebSocket to AWS
  IoT, topics `production-qc/<your user id>/<device>/...`
  (`live_measurement`, `nano_info`, `filter_info`, `notify`).

No third-party Python packages are required.

## Troubleshooting

- Download diagnostics from the integration's device page; personal
  identifiers are redacted.
- Enable debug logging:

```yaml
logger:
  logs:
    custom_components.qc_nano: debug
```

## License

MIT, see [LICENSE](LICENSE).
