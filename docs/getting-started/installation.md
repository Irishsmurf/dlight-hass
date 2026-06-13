# Installation

The dLight integration ships as a Home Assistant **custom component**. The recommended path is HACS, which handles updates for you; a manual copy works too.

## Prerequisites

- A running **Home Assistant** instance (2025.1.0 or newer is the validated target; 2024.1+ generally works).
- One or more **dLight lamps already joined to your local Wi-Fi network**.
- Home Assistant and the lamps on the **same subnet**, so UDP discovery broadcasts can reach them.

!!! note "Provisioning happens elsewhere"
    Home Assistant does not provision the lamp onto Wi-Fi. Use the **Google Home app** (or the vendor app) to put the lamp on your network first. Once it has an IP address, this integration can discover and control it.

## HACS (recommended)

1. Open **HACS** in Home Assistant.
2. Use the **⋮** menu → **Custom repositories**, and add:
   - **Repository:** `https://github.com/Irishsmurf/dlight-hass`
   - **Type:** *Integration*
3. Search HACS for **dLight** and click **Download**.
4. **Restart Home Assistant.**

HACS installs the `dlight.zip` release asset, which bundles the integration code **and** its brand assets (logo/icon). From Home Assistant 2026.3+, those brand files are served locally, so the dLight icon appears without any external submission.

!!! tip "Already in the HACS default list?"
    If the integration is available in the HACS default store, you can skip the custom-repository step and search for it directly.

## Manual

1. Download the latest **`dlight.zip`** from the [Releases page](https://github.com/Irishsmurf/dlight-hass/releases).
2. Unzip it and copy the resulting folder to:
   ```
   <config>/custom_components/dlight/
   ```
   The `manifest.json` should end up at `<config>/custom_components/dlight/manifest.json`.
3. **Restart Home Assistant.**

!!! warning "Keep `brand/` intact"
    The `brand/` directory inside `custom_components/dlight/` must stay where it is — Home Assistant serves the integration icon from exactly that path. Don't delete or relocate it.

## Verify the install

After restarting, go to **Settings → Devices & Services → + Add Integration** and search for **dLight**. If it appears in the list, the component loaded correctly. Continue to [Configuration](configuration.md).

If it does **not** appear, check **Settings → System → Logs** for a `custom_components.dlight` error, and confirm the files landed at the path above.

## Updating

- **HACS:** updates surface in the HACS dashboard; download the new version and restart.
- **Manual:** download the newer `dlight.zip`, replace the `custom_components/dlight/` folder, and restart.

Releases follow [semantic versioning](https://semver.org/); pre-release tags (e.g. `v1.7.0-rc1`) are published as GitHub pre-releases.
