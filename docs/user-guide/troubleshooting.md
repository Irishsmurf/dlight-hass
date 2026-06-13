# Troubleshooting

Most issues come down to network reachability between Home Assistant and the lamp. Work through the relevant section below.

## The integration isn't in the Add list

- Confirm the files are at `<config>/custom_components/dlight/manifest.json`.
- **Restart Home Assistant** after installing (a reload is not enough for a new integration).
- Check **Settings → System → Logs** for a `custom_components.dlight` load error.

## Discovery finds no lamps

Discovery is a UDP broadcast with a short listen window. It can come up empty when:

- The lamp **isn't provisioned** onto Wi-Fi yet (do this in the Google Home app first).
- Home Assistant and the lamp are on **different subnets / VLANs**, so the broadcast doesn't reach.
- Home Assistant runs in a **container/VM without host networking**, blocking broadcast traffic.
- The lamp is briefly **busy** and missed the window — retry the scan.

**Workaround:** add the lamp manually. Find its IP in your router's client list and its device ID on the lamp's label, then use the **Manually add a device** step. See [Configuration](../getting-started/configuration.md#manual-step).

## "Failed to connect to the lamp"

Shown when the validation probe can't reach the lamp during setup or reconfigure. Check that:

- The **IP address** is correct and current (DHCP may have changed it).
- The **device ID** matches the lamp's label exactly.
- The lamp is **powered on** and connected to Wi-Fi.
- Nothing (firewall, client isolation / "AP isolation" on the router) blocks TCP from Home Assistant to the lamp.

## The light shows "Unavailable"

The light goes unavailable when a poll fails. This is usually transient (a dropped packet) and clears on the next successful poll. If it persists:

- Verify the lamp is online — ping its IP, or check the router.
- Look at the **Connectivity** binary sensor; it stays available and reports *disconnected*, confirming the integration sees the lamp as unreachable.
- If the lamp's **IP changed**, the integration's [self-healing](../getting-started/configuration.md#ip-self-healing) should recover it within a few poll intervals via a rediscovery sweep. To force it, re-run **Add Integration** or use **Reconfigure**.

## A lamp's IP changed and didn't recover

Self-healing covers most cases automatically. To recover manually:

1. **Settings → Devices & Services → dLight → ⋮ → Reconfigure**, and enter the new IP, **or**
2. Re-run **+ Add Integration** — discovery will heal the stored address for a known lamp.

To make IPs stable in the first place, set a **DHCP reservation** for each lamp's MAC address in your router.

## Commands feel laggy or "snap back"

- The UI updates optimistically and reconciles on the next poll (default **30 s**). A brief settle is normal.
- Rapid slider drags are protected by a rapid-fire guard so they shouldn't revert mid-interaction. If you see persistent snap-backs, capture [diagnostics](diagnostics.md) and open an issue.

## Transitions look choppy

Transitions are [emulated](transitions.md), not hardware ramps — they're a sequence of discrete steps. Very short transitions look like a single jump; that's expected.

## Still stuck? File a bug

1. Reproduce the problem.
2. Download **diagnostics** for the device (IP and device ID are redacted automatically) — see [Diagnostics & Bug Reports](diagnostics.md).
3. Grab relevant lines from **Settings → System → Logs** (enable debug logging if needed):
   ```yaml title="configuration.yaml — enable debug logs"
   logger:
     default: info
     logs:
       custom_components.dlight: debug
       dlightclient: debug
   ```
4. Open an issue on [GitHub](https://github.com/Irishsmurf/dlight-hass/issues) with the diagnostics, logs, and your Home Assistant version.
