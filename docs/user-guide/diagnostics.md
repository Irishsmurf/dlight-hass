# Diagnostics & Bug Reports

Home Assistant can export a **sanitized snapshot** of a dLight entry to attach to bug reports, so you don't have to hand-collect logs or worry about leaking your network details.

## Download diagnostics

1. **Settings → Devices & Services → dLight**.
2. Open the **device** page for the lamp.
3. Click the **⋮** menu → **Download diagnostics**.

A JSON file downloads to your computer.

## What's included

The snapshot contains just enough to debug, and nothing that identifies you:

| Field | Contents |
|---|---|
| `entry.data` | Config entry data, **with IP address and device ID redacted**. |
| `entry.options` | Entry options (there are none; the integration has no options flow). |
| `device_info` | Model, firmware, and hardware versions reported by the lamp. |
| `state` | The last polled state — on/off, brightness, color temperature. |
| `last_update_success` | Whether the most recent poll succeeded. |
| `update_interval` | The poll interval (30 s). |

## What's redacted

The **IP address** and **device ID** are scrubbed automatically before the file is written, so it's safe to share publicly on a GitHub issue.

```json title="Example (redacted) snapshot"
{
  "entry": {
    "data": { "ip_address": "**REDACTED**", "device_id": "**REDACTED**" },
    "options": {}
  },
  "device_info": {
    "swVersion": "1.0.12",
    "hwVersion": "1.0.0",
    "deviceModel": "dLight",
    "macAddress": "aa:bb:cc:dd:ee:ff"
  },
  "state": { "on": true, "brightness": 80, "color": { "temperature": 4000 } },
  "last_update_success": true,
  "update_interval": "0:00:30"
}
```

!!! note "MAC address"
    `device_info.macAddress` is included because it's used for device-registry integration and DHCP self-healing. If you'd rather not share it, redact that one line by hand before posting.

## Filing a good bug report

Pair the diagnostics with:

- A clear description and **steps to reproduce**.
- Relevant **log lines** (enable `custom_components.dlight: debug` — see [Troubleshooting](troubleshooting.md#still-stuck-file-a-bug)).
- Your **Home Assistant version** and how you installed the integration (HACS or manual).

Open it at **[github.com/Irishsmurf/dlight-hass/issues](https://github.com/Irishsmurf/dlight-hass/issues)**.
