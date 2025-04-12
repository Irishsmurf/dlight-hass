# dLight Home Assistant Integration (`dlight`)

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration) This is a custom integration for Home Assistant to control Google dLight smart lamps locally using the `dlight-client` Python library, which is based on the reverse-engineered local network API.

* **Use this integration at your own risk.**
* This integration is provided for personal/experimental use and carries no official support or warranty from Google or the integration author.
* Future dLight firmware updates could break this integration without notice.

## Prerequisites

* A running Home Assistant instance (check compatibility if specified in `manifest.json`).
* One or more dLight devices connected to your **local Wi-Fi network**.
    * *Note:* You must first get the dLight onto your Wi-Fi. This integration **does not** handle the initial Wi-Fi provisioning (SSID Connect). You need to do that first using methods like the Google Home App setup or the `provision_dlight.py` script discussed previously.
* The **IP Address** and **Device ID** for each dLight device you want to add.
    * You can find these using the UDP discovery feature of the `dlight-client` library (by running `python dlightclient/dlight.py` from its project directory) or potentially from your router's client list.

## Installation

You can install this custom component using HACS (recommended) or manually.

**Manual Installation**

1.  Download the latest release or clone the repository containing this integration.
2.  Copy the entire `dlight` directory into your Home Assistant `<config>/custom_components/` directory. Create `custom_components` if it doesn't exist.
    * Your final structure should look like `<config>/custom_components/dlight/__init__.py`, etc.
3.  Clone https://github.com/Irishsmurf/dlight-client and move dlight-client/dlightclient directory into `<config>/custom_components/dlight/`
    * `cd config/custom_components/dlight/`
    * `git clone https://github.com/Irishsmurf/dlight-client`
    * `mv dlight-client/dlightclient .`
3.  **Restart Home Assistant.**

## Configuration

Configuration is done via the Home Assistant UI (Config Flow):

1.  Go to **Settings** -> **Devices & Services**.
2.  Click the **+ Add Integration** button (bottom right).
3.  Search for "dLight Integration" (or the name you set in `manifest.json`).
4.  Follow the prompts:
    * Enter the **IP Address** of your dLight.
    * Enter the **Device ID** of your dLight (e.g., `QvuTVFlw`).
    * Optionally, enter a friendly **Name** for the device in Home Assistant (if left blank, it might use the model or Device ID).
5.  Click Submit. The integration will attempt to validate the connection.
6.  If successful, the dLight device and its associated light entity will be added.
7.  Repeat for each dLight device you want to add.

## Features

* **Light Entity:** Creates a standard Home Assistant `light` entity for each configured dLight.
* **Control:**
    * Turn On / Off
    * Set Brightness (0-100%, converted to HA's 0-255 scale)
    * Set Color Temperature (2600K - 6000K)
* **State Reporting:** Polls the device periodically (default 30 seconds) to update the state in Home Assistant.
* **Optimistic Updates:** UI should update immediately when commands are sent.

## Troubleshooting

* **Device Unavailable:**
    * Check if the dLight is powered on and connected to your Wi-Fi.
    * Verify the IP address configured in Home Assistant is still correct (DHCP might change it - consider setting a static IP/DHCP reservation in your router).
    * Check Home Assistant logs (Settings -> System -> Logs) for connection errors related to `dlight`.
* **Discovery Script `PermissionError`:** If running the separate `dlight-client` discovery script fails with permission errors, you likely need to run it with `sudo` or as Administrator (see previous discussions). This does *not* affect the normal operation of the HA integration once configured.
