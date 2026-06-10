# dLight Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)
[![Tests](https://github.com/Irishsmurf/dlight-hass/actions/workflows/tests.yaml/badge.svg)](https://github.com/Irishsmurf/dlight-hass/actions/workflows/tests.yaml)
[![Hassfest](https://github.com/Irishsmurf/dlight-hass/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/Irishsmurf/dlight-hass/actions/workflows/hassfest.yaml)
[![HACS Action](https://github.com/Irishsmurf/dlight-hass/actions/workflows/hacs.yaml/badge.svg)](https://github.com/Irishsmurf/dlight-hass/actions/workflows/hacs.yaml)

## Purpose

This is a custom integration for Home Assistant to control dLight smart lamps locally. It utilizes the `dlight-client` Python library to provide seamless control of your dLight devices without relying on cloud services.

## Features

- **Automatic Discovery:** Automatically find dLight devices on your network.
- **Full Control:** Turn them on/off, adjust brightness (0-100%), and change the color temperature (2600K - 6000K).
- **Local Control:** No cloud dependency, purely local network communication.
- **State Reporting:** Polls the device periodically (configurable, default 30s) to keep states in sync.
- **Optimistic Updates:** Immediate UI response upon command.
- **IP Self-Healing:** If your router hands a lamp a new address, re-running discovery (or re-adding the lamp) updates the stored IP automatically — no need to delete and re-add.
- **Reconfigure Support:** Update a lamp's connection details from the UI (entry menu → Reconfigure).
- **Diagnostics:** Download a sanitized snapshot (IP and device ID redacted) for bug reports.
- **Translations:** English, German, French, Japanese, and Irish.

## Prerequisites

- Home Assistant instance.
- dLight devices connected to your **local Wi-Fi network**.
  - **Note:** Initial Wi-Fi provisioning must be done via the Google Home App or similar before adding to Home Assistant.

## Installation

### HACS (Recommended)

1.  Add this repository as a custom repository in HACS.
2.  Search for "dLight" and install it.
3.  Restart Home Assistant.

### Manual

1.  Download the latest release.
2.  Copy `custom_components/dlight` into your `<config>/custom_components/` directory.
3.  Restart Home Assistant.

## Configuration

Configuration is handled through the Home Assistant UI:

1.  Navigate to **Settings** -> **Devices & Services**.
2.  Click **+ Add Integration**.
3.  Search for **dLight**.
4.  The integration will automatically attempt to **discover** devices.
5.  Select your device from the list or choose to add one manually using its **IP Address** and **Device ID**.

### Options

Per-lamp options are available under **Settings** -> **Devices & Services** -> **dLight** -> **Configure**:

- **Poll interval** (5-600 seconds, default 30): how often Home Assistant asks the lamp for its current state. Lower is snappier; higher is quieter on the network.

If a lamp's IP address changes, use **Reconfigure** from the same menu — or simply re-run **Add Integration**, and discovery will heal the stored address automatically.

## Troubleshooting

- **Device Unavailable:**
  - Ensure the dLight is powered on and connected to your Wi-Fi.
  - Check the Home Assistant logs for connection errors.
  - If the lamp's IP changed, see the Options section above.
- **Manual Configuration:**
  - If discovery fails, you can find the IP and Device ID via your router's client list.
- **Reporting Bugs:**
  - Attach the integration's diagnostics (device page -> **Download diagnostics**); IP addresses and device IDs are redacted automatically.

## Development

- Run the test suite with `pytest` (see `AGENTS.md` for architecture notes).
- `custom_components/dlight/brand/` holds the logo assets required by the HACS brands validation; the long-term home for these is a [home-assistant/brands](https://github.com/home-assistant/brands) submission.
- **Releasing:** bump the version in `manifest.json`, commit, and push a matching `vX.Y.Z` tag — the Release workflow runs the tests, builds `dlight.zip` (what HACS installs), and publishes the GitHub release automatically.

**Disclaimer:**
- Use at your own risk. This is a personal project and carries no official support.
