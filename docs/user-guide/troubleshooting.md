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

### Docker Desktop on Windows or macOS

This is the most common reason discovery never works. Docker Desktop runs your containers inside a **WSL 2 / Hyper-V Linux VM that sits behind NAT**, so:

- The lamp's UDP discovery **broadcast can't cross the NAT** into the VM, and the container can't broadcast onto your physical LAN — `discover_devices()` hears nothing.
- `--network host` / `network_mode: host` **does not help here** — on Docker Desktop "host" is the Linux VM's network, not your Windows/macOS LAN adapter. (It only enables LAN broadcast on a real Linux host.)
- Outbound **unicast TCP** to the lamp's IP *does* traverse the NAT — which is why **manual entry works fine** even though discovery doesn't.

The same limitation means [IP self-healing](../getting-started/configuration.md#ip-self-healing) can't work either (it relies on UDP discovery or HA seeing DHCP leases). So:

1. **Add the lamp manually** (IP + Device ID) — fully supported, and the right path for this setup.
2. **Set a DHCP reservation** in your router for the lamp's MAC so its IP never changes — otherwise a new lease will silently take the lamp offline with no way to auto-recover.
3. If you specifically want discovery and self-healing to work, run HA where it has a real LAN presence instead: **Home Assistant OS in a VM with a bridged network adapter**, or HA in Docker on a **Linux** host/Raspberry Pi with `network_mode: host`.

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

### Reading the Connectivity sensor attributes

The **Connectivity** binary sensor exposes health metrics in its state attributes. In **Developer Tools → States**, look for `binary_sensor.{name}_connectivity`:

| Attribute | What it tells you |
|---|---|
| `consecutive_failures` | How many polls have failed in a row. Resets to `0` on success. |
| `last_successful_poll` | Timestamp of the last poll that got a response. `None` until the first success. |
| `rediscovery_triggered` | `true` after 3 consecutive failures — a UDP rediscovery sweep is in flight. |
| `poll_interval_seconds` | How frequently the lamp is polled (default 30 s). |

A lamp that's been offline for 3 polls (~90 s) automatically triggers a rediscovery sweep. If it answers from a new IP, the entry is updated and the coordinator resumes without any manual steps.

## A lamp's IP changed and didn't recover

Self-healing covers most cases automatically. To recover manually:

1. **Settings → Devices & Services → dLight → ⋮ → Reconfigure**, and enter the new IP, **or**
2. Re-run **+ Add Integration** — discovery will heal the stored address for a known lamp.

To make IPs stable in the first place, set a **DHCP reservation** for each lamp's MAC address in your router.

## Commands feel laggy or "snap back"

- The UI updates optimistically and reconciles on the next poll (default **30 s**). A brief settle is normal.
- Rapid slider drags are protected by a rapid-fire guard so they shouldn't revert mid-interaction. If you see persistent snap-backs, capture [diagnostics](diagnostics.md) and open an issue.

## Physical button presses don't trigger automations fast enough

State changes from physical buttons are only detected on the next poll (up to 30 s later). If you need instant reaction, use the **`dlight_physical_control`** event instead of a state trigger — it fires the moment the next poll detects a change.

See [Physical Control Event](physical-control-event.md) for event payload details and automation examples.

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
4. If you can reproduce the issue reliably, consider running [`tests/fake_lamp.py`](https://github.com/Irishsmurf/dlight-hass/blob/main/tests/fake_lamp.py) — a simulated lamp with injectable delays, resets, and hangs — to capture the exact behaviour without involving a physical device.
5. Open an issue on [GitHub](https://github.com/Irishsmurf/dlight-hass/issues) with the diagnostics, logs, your Home Assistant version, and the `dlight-client` version shown in **Settings → System → Repairs** or `pip show dlight-client`.
