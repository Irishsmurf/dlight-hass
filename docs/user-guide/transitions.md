# Transitions

Home Assistant lets you request a smooth fade with the `transition:` parameter on `light.turn_on` / `light.turn_off`. The dLight protocol has **no native fade** command — so the integration **emulates** transitions by stepping the lamp toward the target itself.

## How emulation works

![The brightness and color-temperature axes a fade can move along: 2600 K warm to 6000 K cool](../assets/color-temperature.svg){ loading=lazy }

When you pass a transition, a cancellable **background task** walks brightness and/or color temperature from the current value to the target in small steps:

- Steps fire roughly every **0.5 s** (`TRANSITION_STEP_INTERVAL`), comfortable for the lamp's single TCP socket.
- A transition is sliced into at most **60 steps** (`TRANSITION_MAX_STEPS`); longer fades stretch the interval rather than flooding the lamp with commands.
- Each step updates the **optimistic state**, so the UI animates along with the lamp.
- Steps only send what actually **changed** since the previous step — a slow fade won't resend identical values every half-second.
- The final step always lands **exactly** on the requested target.

```yaml title="Example: 5-second fade up to warm 40%"
service: light.turn_on
target:
  entity_id: light.desk_lamp
data:
  brightness_pct: 40
  color_temp_kelvin: 2700
  transition: 5
```

## Fade to off

`light.turn_off` with a transition fades brightness **down to a 1 % floor first**, then sends the actual power-off command. (Setting brightness to 0 % is indistinguishable from "off" and would end the fade early, so the fade bottoms out at 1 % before powering down.)

## The newest command always wins

At most one fade runs per lamp at a time. **Any** new command — another transition, a plain on/off, a brightness change, or pressing Identify — cancels the in-flight fade before doing anything else. So if you start a 10-minute sunset fade and then tap the lamp off, the off wins immediately.

## Behavior notes & limits

- **Unknown starting point:** if the lamp's current state is unknown, or nothing would actually change, the integration skips emulation and applies the change instantly instead.
- **Errors mid-fade:** because a fade runs in the background, a device error during one can't be delivered to a service call — it's logged, the optimistic guess is cleared, and the next poll reconciles whatever the lamp actually reached.
- **Not perfectly smooth:** emulation is a series of discrete steps, not a hardware ramp. Very short transitions (under ~1 s) will look like a single jump.

The full implementation and the reconciliation rules around it are covered in [Light Entity & Optimistic State](../architecture/light-entity.md).
