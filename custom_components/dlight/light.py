"""Light platform for dLight.

The heavy lifting (device handle, polling) happens in __init__.py and
coordinator.py; this module only defines the entity. DLightEntity is a thin
read-only view over the coordinator's cache, with one twist — *optimistic*
state. Commands (turn on, set brightness, ...) update the entity's state
immediately so the UI feels instant; the next confirmed poll replaces the
guess with the device's reported truth.

Rapid-fire guard: after each command, optimistic state is protected for one
full poll interval.  A poll arriving within this window is compared against
the optimistic expectation — if the lamp confirms the command (polled state
matches what we asked for), optimistic state is cleared immediately for
instant UI confirmation.  If the poll returns stale data (state mismatch),
it is ignored so the UI doesn't snap back.  Once the window expires, any
poll clears the override regardless.

Transitions: the lamp protocol has no native fade, so `transition:` is
emulated — a background task walks brightness/temperature toward the target
in small steps. The task is cancelled by any newer command, so the latest
request always wins.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from contextlib import suppress
from typing import Any

from dlightclient import DLightDevice

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, EVENT_PHYSICAL_CONTROL, KELVIN_MAX, KELVIN_MIN, MIN_BRIGHTNESS_PCT, POLL_INTERVAL
from .coordinator import DLightCoordinator

_LOGGER = logging.getLogger(__name__)

# Serialize HA service calls per lamp: rapid UI interactions must not race
# overlapping commands at a single-socket device. Coordinator polling is
# unaffected — this only gates entity commands (turn_on/turn_off).
PARALLEL_UPDATES = 1

# Emulated transition pacing. ~2 commands/sec is comfortable for the lamp's
# single TCP socket; the step cap keeps very long transitions from turning
# into command floods (the interval stretches instead).
TRANSITION_STEP_INTERVAL = 0.5
TRANSITION_MAX_STEPS = 60


def _to_ha_brightness(percent: int) -> int:
    """Scale dLight brightness (0-100%) to HA brightness (0-255).

    Ceiling, not rounding: 50% must map to 128, and any non-zero device
    brightness must stay non-zero in HA (1% -> 3, never 0 = "off").
    """
    return math.ceil(percent / 100 * 255)


def _apply_brightness_floor(pct: int) -> int:
    """Clamp a device-percent brightness to MIN_BRIGHTNESS_PCT."""
    return max(pct, MIN_BRIGHTNESS_PCT)


def _to_dlight_brightness(brightness: int) -> int:
    """Scale HA brightness (0-255) to dLight brightness (0-100%), clamped.

    The mirror of _to_ha_brightness: ceiling keeps 255 -> 100 and 1 -> 1,
    so only an explicit 0 ever lands on 0.
    """
    return max(0, min(100, math.ceil(brightness / 255 * 100)))


def _interpolate_steps(
    start_pct: int | None,
    end_pct: int | None,
    start_kelvin: int | None,
    end_kelvin: int | None,
    count: int,
) -> list[tuple[int | None, int | None]]:
    """Build per-step (brightness%, kelvin) values for an emulated fade.

    Each tuple holds only what *changed* since the previous step (None means
    "skip this command"), so a slow 10-minute fade doesn't resend identical
    values every half second. An unknown start (None) sends the end value
    once on the first step and dedupes the rest. The final step always lands
    exactly on the requested target.
    """
    steps: list[tuple[int | None, int | None]] = []
    last_pct = start_pct
    last_kelvin = start_kelvin
    for i in range(1, count + 1):
        fraction = i / count
        pct: int | None = None
        if end_pct is not None:
            base = start_pct if start_pct is not None else end_pct
            value = round(base + (end_pct - base) * fraction)
            if value != last_pct:
                pct = last_pct = value
        kelvin: int | None = None
        if end_kelvin is not None:
            base = start_kelvin if start_kelvin is not None else end_kelvin
            value = round(base + (end_kelvin - base) * fraction)
            if value != last_kelvin:
                kelvin = last_kelvin = value
        steps.append((pct, kelvin))
    return steps


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[DLightCoordinator],
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the light entity for an already-initialized lamp.

    __init__.async_setup_entry built the coordinator and stored it in
    entry.runtime_data before forwarding here; nothing is created twice.
    """
    coordinator = entry.runtime_data
    async_add_entities([DLightEntity(coordinator, coordinator.device, entry)])


class DLightEntity(CoordinatorEntity[DLightCoordinator], LightEntity):
    """A dLight lamp: coordinator data underneath, optimistic guesses on top.

    Every readable property follows the same rule — if we recently sent a
    command, report what we *asked for* (the `_optimistic_*` overrides);
    otherwise report what the coordinator last *confirmed*. A confirmed poll
    (_handle_coordinator_update) clears the guesses.
    """

    _attr_has_entity_name = True  # entity is named after its device...
    _attr_name = None  # ...with no suffix: it IS the device's main feature
    _attr_supported_color_modes = {ColorMode.COLOR_TEMP}
    _attr_color_mode = ColorMode.COLOR_TEMP
    _attr_min_color_temp_kelvin = KELVIN_MIN
    _attr_max_color_temp_kelvin = KELVIN_MAX
    _attr_supported_features = LightEntityFeature.TRANSITION

    def __init__(
        self,
        coordinator: DLightCoordinator,
        device: DLightDevice,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the entity from its coordinator, device handle and entry."""
        super().__init__(coordinator)
        self.device = device
        self._attr_unique_id = f"dlight_{device.id}"
        self._base_name = entry.title or f"dLight {device.id}"

        # Optimistic overrides. None means "no pending guess, trust the
        # coordinator"; anything else wins until the next confirmed poll.
        self._optimistic_on: bool | None = None
        self._optimistic_brightness: int | None = None  # HA scale, 0-255
        self._optimistic_kelvin: int | None = None

        # Rapid-fire guard: after each command, optimistic state is held for
        # at least one poll interval.  Any poll arriving within this window
        # is stale (the lamp may not have processed the latest command yet).
        self._last_command_time: float = 0.0

        # The currently running emulated fade, if any. At most one exists;
        # every new command cancels it before doing anything else.
        self._transition_task: asyncio.Task | None = None

        # Snapshot of the last coordinator-confirmed state, used to detect
        # physical changes between polls. None until the first poll is accepted.
        self._last_confirmed_data: dict | None = None

        # The registry card is built once: coordinator.info is static
        # (fetched a single time at setup, see DLightCoordinator).
        device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            name=self._base_name,
            manufacturer="dLight (via custom integration)",
            model=coordinator.info.get("deviceModel", "dLight"),
            sw_version=coordinator.info.get("swVersion"),
            hw_version=coordinator.info.get("hwVersion"),
            configuration_url=f"http://{device.ip}",
        )
        if mac := coordinator.info.get("macAddress"):
            device_info["connections"] = {(dr.CONNECTION_NETWORK_MAC, mac)}
        self._attr_device_info = device_info

    # --- State properties: optimistic guess first, coordinator truth second ---

    @property
    def is_on(self) -> bool | None:
        """Return whether the light is on (None if unknown)."""
        if self._optimistic_on is not None:
            return self._optimistic_on
        return (self.coordinator.data or {}).get("on")

    @property
    def brightness(self) -> int | None:
        """Return brightness on HA's 0-255 scale (None if unknown)."""
        if self._optimistic_brightness is not None:
            return self._optimistic_brightness
        percent = (self.coordinator.data or {}).get("brightness")
        return None if percent is None else _to_ha_brightness(percent)

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return color temperature in Kelvin (None if unknown)."""
        if self._optimistic_kelvin is not None:
            return self._optimistic_kelvin
        color = (self.coordinator.data or {}).get("color")
        return color.get("temperature") if isinstance(color, dict) else None

    def _current_pct(self) -> int | None:
        """Current brightness in *device* percent, for fade starting points.

        Prefers the device-native value from the coordinator: deriving it
        from self.brightness would round-trip 0-100 -> 0-255 -> 0-100 and
        skew the scale (50 -> 128 -> 51).
        """
        if self._optimistic_brightness is not None:
            return _to_dlight_brightness(self._optimistic_brightness)
        return (self.coordinator.data or {}).get("brightness")

    # --- Commands ---

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on, optionally adjusting brightness and/or color temperature.

        The lamp has no single "apply this state" command, so the needed
        commands are issued concurrently, then the result is assumed
        optimistically rather than waiting up to a full poll interval.

        With `transition:` the change is emulated by a background fade task
        instead; the service call returns once the fade is scheduled.
        """
        brightness: int | None = kwargs.get(ATTR_BRIGHTNESS)
        kelvin: int | None = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        transition: float | None = kwargs.get(ATTR_TRANSITION)

        _LOGGER.debug(
            "%s: turn_on brightness=%s kelvin=%s transition=%s",
            self.entity_id,
            brightness,
            kelvin,
            transition,
        )

        # HA convention: turn_on with brightness 0 actually means "turn off".
        if brightness is not None and _to_dlight_brightness(brightness) == 0:
            await self.async_turn_off(**kwargs)
            return

        # The newest command always wins over a fade already in flight.
        await self._async_cancel_transition()

        if (
            transition is not None
            and transition > 0
            and self._async_start_turn_on_fade(brightness, kelvin, transition)
        ):
            return

        # Capture current on-state before mutating optimistic properties.
        # Commands accepted: predict the outcome. Values not in this call keep
        # their last known state, with sane defaults when nothing is known.
        was_on = self.is_on
        self._last_command_time = time.monotonic()
        self._optimistic_on = True
        self._optimistic_brightness = (
            brightness if brightness is not None else self.brightness
        )
        if self._optimistic_brightness is None:
            self._optimistic_brightness = 255  # unknown -> assume full
        self._optimistic_kelvin = (
            kelvin if kelvin is not None else self.color_temp_kelvin
        )
        if self._optimistic_kelvin is None:
            self._optimistic_kelvin = KELVIN_MIN  # unknown -> assume warm
        _LOGGER.debug(
            "%s: optimistic state set on=True brightness=%s kelvin=%s",
            self.entity_id,
            self._optimistic_brightness,
            self._optimistic_kelvin,
        )
        self.async_write_ha_state()

        # When both brightness and temperature are set atomically, apply_scene
        # reduces two TCP commands to one and rolls back both on failure.
        commands = []
        if brightness is not None and kelvin is not None:
            commands.append(
                self.device.apply_scene(
                    brightness=_apply_brightness_floor(_to_dlight_brightness(brightness)),
                    temperature=int(kelvin),
                )
            )
        else:
            if brightness is not None:
                commands.append(
                    self.device.set_brightness(
                        _apply_brightness_floor(_to_dlight_brightness(brightness))
                    )
                )
            if kelvin is not None:
                commands.append(self.device.set_color_temperature(int(kelvin)))

        # Setting brightness/temperature implicitly powers the lamp on, so the
        # explicit power command is only needed for a bare turn_on call, or
        # when the lamp is (as far as we know) currently off.
        if not commands or not was_on:
            commands.insert(0, self.device.turn_on())

        try:
            await self._send(commands)
        except Exception as err:
            _LOGGER.exception("Failed to turn on dLight %s", self.device.id)
            self._clear_optimistic_state()
            self.async_write_ha_state()
            # HomeAssistantError, not ServiceValidationError: the user's input
            # was fine — the device couldn't be reached or rejected the command.
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="turn_on_failed",
                translation_placeholders={
                    "device_name": self._base_name,
                    "error": str(err),
                },
            ) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off (optimistically, confirmed by the next poll).

        With `transition:` brightness fades down first, then the power-off
        command is sent by the same background task.
        """
        transition: float | None = kwargs.get(ATTR_TRANSITION)

        _LOGGER.debug("%s: turn_off transition=%s", self.entity_id, transition)

        await self._async_cancel_transition()

        if (
            transition is not None
            and transition > 0
            and self._async_start_turn_off_fade(transition)
        ):
            return

        # Predict "off"; brightness/temperature are meaningless while off.
        self._last_command_time = time.monotonic()
        self._optimistic_on = False
        self._optimistic_brightness = None
        self._optimistic_kelvin = None
        self.async_write_ha_state()

        try:
            async with self.coordinator.command_lock:
                await self.device.turn_off()
        except Exception as err:
            _LOGGER.exception("Failed to turn off dLight %s", self.device.id)
            self._clear_optimistic_state()
            self.async_write_ha_state()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="turn_off_failed",
                translation_placeholders={
                    "device_name": self._base_name,
                    "error": str(err),
                },
            ) from err

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the light using the device's native toggle command."""
        _LOGGER.debug("%s: toggle (currently on=%s)", self.entity_id, self.is_on)
        await self._async_cancel_transition()
        # Update optimistic state
        self._last_command_time = time.monotonic()
        predicted_on = not self.is_on
        self._optimistic_on = predicted_on
        if predicted_on:
            self._optimistic_brightness = self.brightness or 255
            self._optimistic_kelvin = self.color_temp_kelvin or KELVIN_MIN
        else:
            self._optimistic_brightness = None
            self._optimistic_kelvin = None
        self.async_write_ha_state()

        try:
            async with self.coordinator.command_lock:
                await self.device.toggle()
        except Exception as err:
            _LOGGER.exception("Failed to toggle dLight %s", self.device.id)
            self._clear_optimistic_state()
            self.async_write_ha_state()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="toggle_failed",
                translation_placeholders={
                    "device_name": self._base_name,
                    "error": str(err),
                },
            ) from err

    async def _send(self, commands: list) -> None:
        """Run device commands concurrently; raise the first failure, if any.

        gather(return_exceptions=True) lets every command finish before we
        judge the batch — a plain gather would abandon in-flight siblings.
        The coordinator's command_lock keeps the batch from interleaving with
        fade steps or the identify button's flash sequence.
        """
        async with self.coordinator.command_lock:
            results = await asyncio.gather(*commands, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                raise result

    # --- Emulated transitions ---

    @callback
    def _async_start_turn_on_fade(
        self, brightness: int | None, kelvin: int | None, transition: float
    ) -> bool:
        """Schedule a fade toward the requested turn_on target.

        Returns False when fading is impossible (the lamp's current state is
        unknown, or nothing would actually change) so the caller falls back
        to the instant path.
        """
        is_on = self.is_on
        if is_on is None:
            return False  # no starting point to fade from

        current_pct = self._current_pct()

        if brightness is not None:
            end_pct = _to_dlight_brightness(brightness)
        elif not is_on:
            # Bare turn_on from off: fade in to the last known level.
            end_pct = current_pct or 100
        else:
            end_pct = None  # already on, brightness untouched
        start_pct = current_pct if is_on else 0

        end_kelvin = int(kelvin) if kelvin is not None else None
        start_kelvin = self.color_temp_kelvin

        if (end_pct is None or end_pct == start_pct) and (
            end_kelvin is None or end_kelvin == start_kelvin
        ):
            return False  # nothing to fade

        steps, interval = self._fade_plan(
            start_pct, end_pct, start_kelvin, end_kelvin, transition
        )
        self._transition_task = self.hass.async_create_task(
            self._async_run_fade(steps, interval, turn_off_after=False)
        )
        return True

    @callback
    def _async_start_turn_off_fade(self, transition: float) -> bool:
        """Schedule a fade down to minimum brightness followed by power-off.

        Returns False when there is nothing to fade (lamp off/unknown, or
        already at minimum) so the caller sends a plain power-off instead.
        """
        start_pct = self._current_pct()
        if not self.is_on or start_pct is None or start_pct <= MIN_BRIGHTNESS_PCT:
            return False

        steps, interval = self._fade_plan(
            start_pct, MIN_BRIGHTNESS_PCT, None, None, transition
        )
        self._transition_task = self.hass.async_create_task(
            self._async_run_fade(steps, interval, turn_off_after=True)
        )
        return True

    def _fade_plan(
        self,
        start_pct: int | None,
        end_pct: int | None,
        start_kelvin: int | None,
        end_kelvin: int | None,
        transition: float,
    ) -> tuple[list[tuple[int | None, int | None]], float]:
        """Slice a transition into timed steps of interpolated values."""
        count = max(
            1, min(round(transition / TRANSITION_STEP_INTERVAL), TRANSITION_MAX_STEPS)
        )
        interval = transition / count
        steps = _interpolate_steps(start_pct, end_pct, start_kelvin, end_kelvin, count)
        return steps, interval

    async def _async_run_fade(
        self,
        steps: list[tuple[int | None, int | None]],
        interval: float,
        *,
        turn_off_after: bool,
    ) -> None:
        """Walk the lamp through the fade steps; runs as a background task.

        Each step updates the optimistic state so the UI animates along.
        Device errors end the fade with a log entry rather than an exception:
        there is no service call left to deliver it to. A refresh afterwards
        reconciles whatever the lamp actually reached.
        """
        _LOGGER.debug(
            "dLight %s: fade starting (%d steps, interval=%.2fs, turn_off_after=%s)",
            self.device.id,
            len(steps),
            interval,
            turn_off_after,
        )
        try:
            for index, (pct, kelvin) in enumerate(steps):
                if index:
                    await asyncio.sleep(interval)
                _LOGGER.debug(
                    "dLight %s: fade step %d/%d pct=%s kelvin=%s",
                    self.device.id,
                    index + 1,
                    len(steps),
                    pct,
                    kelvin,
                )
                commands = []
                if pct is not None:
                    commands.append(self.device.set_brightness(_apply_brightness_floor(pct)))
                if kelvin is not None:
                    commands.append(self.device.set_color_temperature(kelvin))
                if not commands:
                    continue  # deduplicated step: keep the timing, skip the I/O
                async with self.coordinator.command_lock:
                    await asyncio.gather(*commands)
                self._optimistic_on = True
                if pct is not None:
                    self._optimistic_brightness = _to_ha_brightness(pct)
                if kelvin is not None:
                    self._optimistic_kelvin = kelvin
                self.async_write_ha_state()

            if turn_off_after:
                async with self.coordinator.command_lock:
                    await self.device.turn_off()
                self._optimistic_on = False
                self._optimistic_brightness = None
                self._optimistic_kelvin = None
                self.async_write_ha_state()
        except asyncio.CancelledError:
            raise  # a newer command took over; it owns the state from here
        except Exception:  # noqa: BLE001 — background task: log, don't crash HA
            _LOGGER.warning(
                "Transition failed for dLight %s; falling back to polled state",
                self.device.id,
                exc_info=True,
            )
            self._clear_optimistic_state()
            self.async_write_ha_state()

        # Drop the task reference *before* updating state: _handle_coordinator_update
        # ignores updates while a fade is "active", and this fade is done. Calling
        # _handle_coordinator_update immediately reconciles the optimistic state
        # with the latest state listener data without waiting for another poll.
        self._transition_task = None
        self._handle_coordinator_update()

    async def _async_cancel_transition(self) -> None:
        """Stop any in-flight fade and wait for it to fully unwind."""
        if self._transition_task is not None and not self._transition_task.done():
            self._transition_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._transition_task
        self._transition_task = None

    async def async_added_to_hass(self) -> None:
        """Entity is live: snapshot coordinator state as the physical baseline."""
        await super().async_added_to_hass()
        if self.coordinator.data is not None:
            self._last_confirmed_data = self.coordinator.data

    async def async_will_remove_from_hass(self) -> None:
        """Entity is going away: never leave a fade task running behind it."""
        await self._async_cancel_transition()
        await super().async_will_remove_from_hass()

    # --- Coordinator plumbing ---

    @callback
    def _clear_optimistic_state(self) -> None:
        """Drop all pending guesses; properties fall back to coordinator data."""
        self._optimistic_on = None
        self._optimistic_brightness = None
        self._optimistic_kelvin = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """A confirmed poll arrived: real data replaces any optimistic guess.

        Guards against stale polls in two cases:
          1. A fade is in progress — the fade owns the UI until it finishes.
          2. The last command was sent less than one poll interval ago *and*
             the polled state does not match what we optimistically predicted.
             A matching poll means the lamp confirmed the command — clear
             the optimistic state immediately.  A mismatching poll is stale
             and is ignored so the UI doesn't snap back.

        When a poll arrives outside the hold window and the state has changed
        since the last confirmed update, a dlight_physical_control event is
        fired on the HA event bus (physical button press or external client).
        """
        if self.coordinator.data is None:
            return  # failed poll; availability handling is CoordinatorEntity's job
        if self._transition_task is not None and not self._transition_task.done():
            # Mid-fade a poll is already stale: it would snap the UI back to
            # wherever the lamp was when polled. The fade requests its own
            # refresh on completion.
            _LOGGER.debug("dLight %s: poll rejected (fade in progress)", self.device.id)
            return

        within_hold = (
            self._optimistic_on is not None
            and time.monotonic() - self._last_command_time < POLL_INTERVAL
        )

        if within_hold:
            data = self.coordinator.data
            polled_on = data.get("on")
            polled_brightness = data.get("brightness")
            polled_kelvin = (
                data.get("color", {}).get("temperature")
                if isinstance(data.get("color"), dict)
                else None
            )

            matches = True
            if self._optimistic_on != polled_on:
                matches = False
            if self._optimistic_brightness is not None:
                if (
                    _to_dlight_brightness(self._optimistic_brightness)
                    != polled_brightness
                ):
                    matches = False
            if (
                self._optimistic_kelvin is not None
                and self._optimistic_kelvin != polled_kelvin
            ):
                matches = False

            if not matches:
                # Within the hold window and state doesn't match: ignore
                # this poll to prevent the UI from snapping back to a stale
                # value during rapid-fire interactions.
                _LOGGER.debug(
                    "dLight %s: poll rejected (stale within hold window)", self.device.id
                )
                return
            # Matching poll confirms the HA command — fall through to update.
            _LOGGER.debug("dLight %s: poll accepted (confirmed HA command)", self.device.id)
        else:
            # Outside the hold window: any change was driven externally.
            if self._last_confirmed_data is not None:
                _LOGGER.debug(
                    "dLight %s: physical control detected (outside hold window)", self.device.id
                )
                self._fire_physical_control_event(
                    self._last_confirmed_data, self.coordinator.data
                )

        self._last_confirmed_data = self.coordinator.data
        self._clear_optimistic_state()
        super()._handle_coordinator_update()

    @callback
    def _fire_physical_control_event(self, prev: dict, new: dict) -> None:
        """Fire EVENT_PHYSICAL_CONTROL when a poll reveals an external state change."""
        prev_on = prev.get("on")
        new_on = new.get("on")
        prev_brightness = prev.get("brightness")
        new_brightness = new.get("brightness")
        prev_kelvin = (
            prev.get("color", {}).get("temperature")
            if isinstance(prev.get("color"), dict)
            else None
        )
        new_kelvin = (
            new.get("color", {}).get("temperature")
            if isinstance(new.get("color"), dict)
            else None
        )

        if (
            prev_on == new_on
            and prev_brightness == new_brightness
            and prev_kelvin == new_kelvin
        ):
            return  # poll was a no-op; nothing to report

        if prev_on != new_on:
            action = "turned_on" if new_on else "turned_off"
        else:
            action = "changed"

        self.hass.bus.async_fire(
            EVENT_PHYSICAL_CONTROL,
            {
                "device_id": self.device.id,
                "entity_id": self.entity_id,
                "action": action,
                "previous_state": prev,
                "new_state": new,
            },
        )
        _LOGGER.debug(
            "dLight %s: physical control detected (%s)", self.device.id, action
        )
