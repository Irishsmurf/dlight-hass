# Physical Control Event

When someone physically presses a button on a dLight lamp — or changes its state via a third-party app — Home Assistant has no push path to learn about it instantly. The coordinator solves this by comparing each polled state against the last known state and firing an event whenever a change wasn't initiated by HA itself.

This event lets you build automations that **react to physical interactions** with your lamp.

---

## What fires the event

The `dlight_physical_control` event fires when:

1. A coordinator poll returns a state that differs from the previous confirmed state **and**
2. The change happened **outside the optimistic hold window** — i.e., HA did not send a command in the last 30 seconds that could explain it.

This means the event does **not** fire for:

- Commands you sent from HA (turn on, set brightness, automations, etc.)
- Polls arriving while a transition/fade is in progress
- Polls where nothing changed

---

## Event payload

| Field | Type | Description |
|---|---|---|
| `device_id` | `str` | The dLight device ID (e.g. `abc123`) |
| `entity_id` | `str` | The light entity that detected the change (e.g. `light.desk_lamp`) |
| `action` | `str` | `"turned_on"`, `"turned_off"`, or `"changed"` |
| `previous_state` | `dict` | The coordinator's last confirmed state before the change |
| `new_state` | `dict` | The freshly polled state after the change |

### Example payload

```json
{
  "device_id": "abc123",
  "entity_id": "light.desk_lamp",
  "action": "turned_on",
  "previous_state": {
    "on": false,
    "brightness": null,
    "color": { "temperature": 4000 }
  },
  "new_state": {
    "on": true,
    "brightness": 80,
    "color": { "temperature": 4000 }
  }
}
```

---

## Physical Control entity

In addition to the bus event, each lamp device exposes a **Physical control** entity (`event` platform, device class `button`, diagnostic category). It appears under the device in the HA UI and updates each time a physical interaction is detected.

This entity can be used directly as an **event trigger** in automations — no template required.

---

## Automation examples

### 1. Notify when the lamp is physically turned on

```yaml
automation:
  alias: "Desk Lamp — physical on notification"
  trigger:
    - platform: event
      event_type: dlight_physical_control
      event_data:
        device_id: "abc123"
        action: "turned_on"
  action:
    - service: notify.mobile_app_my_phone
      data:
        message: "Desk lamp was turned on physically."
```

### 2. Turn off all other lights when the lamp is physically turned off

```yaml
automation:
  alias: "Desk Lamp — physical off cascades"
  trigger:
    - platform: event
      event_type: dlight_physical_control
      event_data:
        device_id: "abc123"
        action: "turned_off"
  action:
    - service: light.turn_off
      target:
        area_id: office
```

### 3. Log brightness changes to a helper

```yaml
automation:
  alias: "Desk Lamp — log brightness changes"
  trigger:
    - platform: event
      event_type: dlight_physical_control
      event_data:
        device_id: "abc123"
        action: "changed"
  action:
    - service: input_text.set_value
      target:
        entity_id: input_text.lamp_last_brightness_change
      data:
        value: >
          {{ trigger.event.data.new_state.brightness }}% at {{ now().strftime('%H:%M') }}
```

### 4. Using the Physical Control entity trigger (UI-friendly)

```yaml
automation:
  alias: "Desk Lamp — entity event trigger"
  trigger:
    - platform: state
      entity_id: event.desk_lamp_physical_control
  action:
    - service: notify.mobile_app_my_phone
      data:
        message: >
          Desk lamp: {{ trigger.to_state.attributes.event_type }}
```

---

## Limitations

- **Detection latency** — the minimum latency is one full poll cycle (default **30 seconds**). This event is not suitable for real-time triggers.
- **No push path** — dLight lamps communicate via TCP command/response only; there is no mechanism for the lamp to push unsolicited state changes to HA.
- **Hold window** — changes detected within 30 seconds of an HA-initiated command are suppressed to avoid false positives from slow confirmations.
