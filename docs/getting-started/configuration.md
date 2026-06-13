# Configuration

dLight is configured **entirely through the Home Assistant UI** — there is no YAML configuration and no options to tune. Each physical lamp becomes **one config entry**, identified by a unique ID of `dlight_<device_id>`.

## Add a lamp

1. Go to **Settings → Devices & Services**.
2. Click **+ Add Integration** and search for **dLight**.
3. The integration runs a brief (~2 second) UDP discovery sweep **in the background** — there is no separate "scanning…" screen. What you see next depends on whether it found anything:
   - **Lamps found** → a pick-list of discovered lamps (see [Discovery step](#discovery-step)).
   - **Nothing found** → the manual entry form opens directly (see [Manual step](#manual-step)).

!!! warning "Went straight to an IP / Device ID form? That's expected."
    If the dialog jumps directly to asking for an **IP address** and **Device ID**, discovery found **no lamps** on your network, so it fell back to manual entry. There is no separate scan screen and no *"Manually add a device"* button on its own — that option only appears **inside** the discovery pick-list, which isn't shown when nothing is discovered.

    Discovery commonly finds nothing when Home Assistant runs in **Docker/a container or VM without host networking**, when HA and the lamp are on **different subnets/VLANs**, or when the lamp **isn't on Wi-Fi yet**. You can fill in the manual form to add the lamp anyway — see [Discovery finds no lamps](../user-guide/troubleshooting.md#discovery-finds-no-lamps) to fix discovery itself.

### Discovery step

When one or more lamps answer the broadcast, you get a pick-list showing each as `<model> (<ip>)`, **plus a final *"Manually add a device"* entry** to bypass discovery. Selecting a lamp pre-fills the manual form, which validates the connection before creating the entry.

### Manual step

This is where you land when discovery finds nothing — or reach by choosing *"Manually add a device"* in the pick-list. Provide:

| Field | Required | Description |
|---|---|---|
| **IP address** | ✅ | The lamp's IPv4 address on your LAN. Find it in your router's client list. |
| **Device ID** | ✅ | Printed on the lamp's label, or shown in the dLight app. |
| **Name** | ⬜ | Optional friendly name. Defaults to the model the lamp reports. |

When you submit, the integration **probes the lamp once** to confirm the IP/device-ID pair works. If it can't reach the lamp, you'll see *"Failed to connect…"* — double-check the address and that the lamp is powered.

## What gets created

Adding a lamp creates a single **device** with these entities:

![The device card created for a dLight lamp, with its Light, Identify, and Connectivity entities](../assets/entities.svg){ width=520 loading=lazy }

| Entity | Platform | Purpose |
|---|---|---|
| **Light** | `light` | The main control: on/off, brightness, color temperature. |
| **Identify** button | `button` | Flashes the lamp so you can tell which physical device it is. *(Diagnostic)* |
| **Connectivity** sensor | `binary_sensor` | Reports whether the last poll reached the lamp. *(Diagnostic)* |

See [Features](../user-guide/features.md) for what each one does in detail.

## Reconfigure a lamp

If a lamp's connection details change, you usually don't need to do anything — see [IP self-healing](#ip-self-healing) below. To edit details by hand:

1. **Settings → Devices & Services → dLight**.
2. On the entry, open the **⋮** menu → **Reconfigure**.
3. Update the IP address (or other fields) and submit.

Reconfigure must keep pointing at the **same physical lamp** — entering a different device ID is rejected, because that would describe a different lamp (add it as a new entry instead).

## IP self-healing

DHCP routers reassign addresses over time. This integration recovers from that automatically through **three** independent paths, so a changed IP rarely needs manual intervention:

1. **DHCP watcher** — the manifest registers a `dhcp` matcher for already-known devices. When a configured lamp renews its lease, Home Assistant notifies the integration, which updates the stored IP and reloads the entry.
2. **Runtime rediscovery sweep** — if a lamp stops answering polls for several consecutive intervals, the coordinator fires a one-shot UDP discovery sweep. If the lamp replies from a new address, the entry self-heals. This covers setups where Home Assistant can't see the DHCP lease.
3. **Re-running setup / discovery** — manually re-adding a known lamp, or re-running **Add Integration**, refreshes its stored IP as a side effect.

In every case the config entry is updated and reloaded so the running coordinator targets the new address — no delete-and-re-add required.

!!! info "How it works under the hood"
    The mechanics live in [Config Flow & IP Self-Healing](../architecture/config-flow.md) and [Coordinator & Polling](../architecture/coordinator.md).

## Localization

The UI is translated into **English, German, French, Japanese, and Irish**. Home Assistant picks the language from your profile. To add or fix a translation, see [Localization](../contributing/localization.md).
