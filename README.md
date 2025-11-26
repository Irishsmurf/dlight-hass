# dLight Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)

## Purpose

This is a custom integration for Home Assistant to control dLight smart lamps locally. It utilizes the `dlight-client` Python library, which is based on the reverse-engineered local network API, to provide seamless control of your dLight devices without relying on cloud services. This integration allows you to:

- **Control your dLights directly from Home Assistant:** Turn them on/off, adjust brightness, and change the color temperature.
- **Automate your lighting:** Create automations and scenes in Home Assistant that include your dLights.
- **Monitor the state of your dLights:** See at a glance whether your lights are on or off, and what their current brightness and color temperature are.

**Disclaimer:**
* **Use this integration at your own risk.**
* This integration is provided for personal/experimental use and carries no official support.
* Future dLight firmware updates could break this integration without notice.

## Prerequisites

Before you begin, ensure you have the following:

* A running Home Assistant instance.
* One or more dLight devices connected to your **local Wi--Fi network**.
  * **Note:** This integration does not handle the initial Wi-Fi provisioning of your dLight devices. You must first connect them to your network using the Google Home App or another method.
* The **IP Address** and **Device ID** for each dLight device you wish to add.
  * You can find these using the UDP discovery feature of the `dlight-client` library or by checking the client list on your router.

## Installation

You can install this custom component using HACS (recommended) or manually.

### HACS Installation (Recommended)

1.  Add this repository as a custom repository in HACS.
2.  Search for "dLight Integration" and install it.
3.  Restart Home Assistant.

### Manual Installation

1.  Download the latest release or clone this repository.
2.  Copy the entire `custom_components/dlight-hass` directory into your Home Assistant `<config>/custom_components/` directory. You may need to create the `custom_components` directory if it doesn't exist.
3.  Restart Home Assistant.

## Configuration

Configuration is handled through the Home Assistant UI:

1.  Navigate to **Settings** -> **Devices & Services**.
2.  Click the **+ Add Integration** button.
3.  Search for "dLight" and select it.
4.  Follow the on-screen prompts to enter the **IP Address**, **Device ID**, and an optional **Name** for your dLight device.
5.  Click **Submit**. The integration will validate the connection and add the device.
6.  Repeat the process for each additional dLight device.

## Features

*   **Light Entity:** Creates a standard Home Assistant `light` entity for each configured dLight.
*   **Control:**
    *   Turn On / Off
    *   Set Brightness (0-100%, converted to Home Assistant's 0-255 scale)
    *   Set Color Temperature (2600K - 6000K)
*   **State Reporting:** Polls the device periodically (default 30 seconds) to update the state in Home Assistant.
*   **Optimistic Updates:** The UI updates immediately when commands are sent, providing a responsive experience.

## Troubleshooting

*   **Device Unavailable:**
    *   Ensure the dLight is powered on and connected to your Wi-Fi.
    *   Verify that the IP address configured in Home Assistant is correct. Consider setting a static IP address or DHCP reservation for your dLight in your router's settings.
    *   Check the Home Assistant logs (**Settings** -> **System** -> **Logs**) for any connection errors related to the `dlight` integration.
*   **Discovery Script `PermissionError`:** If you are using the `dlight-client` discovery script and encounter permission errors, you may need to run it with `sudo` or as an administrator. This does not affect the operation of the Home Assistant integration itself.
