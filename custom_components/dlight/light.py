"""Light platform for dLight.

Architecture in one paragraph: a DLightCoordinator reads the lamp's static
identity (model, firmware) once at setup, then polls only its state every
UPDATE_INTERVAL. DLightEntity is a thin read-only view over that cache, with
one twist — *optimistic* state. Commands (turn on, set brightness, ...)
update the entity's state immediately so the UI feels instant; the next
confirmed poll replaces the guess with the device's reported truth.
"""
from __future__ import annotations

import asyncio
import logging
import math
from typing import Any

from dlightclient import (
    STATUS_SUCCESS,
    AsyncDLightClient,
    DLightDevice,
    DLightError,
)

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_DEVICE_ID,
    DOMAIN,
    KELVIN_MAX,
    KELVIN_MIN,
    POLL_TIMEOUT,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def _to_ha_brightness(percent: int) -> int:
    """Scale dLight brightness (0-100%) to HA brightness (0-255).

    Ceiling, not rounding: 50% must map to 128, and any non-zero device
    brightness must stay non-zero in HA (1% -> 3, never 0 = "off").
    """
    return math.ceil(percent / 100 * 255)


def _to_dlight_brightness(brightness: int) -> int:
    """Scale HA brightness (0-255) to dLight brightness (0-100%), clamped.

    The mirror of _to_ha_brightness: ceiling keeps 255 -> 100 and 1 -> 1,
    so only an explicit 0 ever lands on 0.
    """
    return max(0, min(100, math.ceil(brightness / 255 * 100)))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Wire up one lamp: build the device handle, prime the coordinator, add the entity."""
    ip_address = entry.data.get(CONF_IP_ADDRESS)
    device_id = entry.data.get(CONF_DEVICE_ID)
    if not ip_address or not device_id:
        _LOGGER.error(
            "Config entry %s is missing IP address or device ID", entry.entry_id
        )
        return

    device = DLightDevice(
        ip_address=ip_address, device_id=device_id, client=AsyncDLightClient()
    )
    name = entry.title or f"dLight {device_id}"
    _LOGGER.debug("Setting up dLight device: %s", device)

    coordinator = DLightCoordinator(hass, device, name)
    # Fetch once before adding the entity, so it never appears with unknown
    # state; raises ConfigEntryNotReady (auto-retry) if the lamp is offline.
    await coordinator.async_config_entry_first_refresh()

    # Published for other platforms and the test suite.
    hass.data[DOMAIN][entry.entry_id] = coordinator

    async_add_entities([DLightEntity(coordinator, device, entry)])


class DLightCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Owns all communication with one lamp.

    Two payloads, two cadences:
      * get_info  -> model / firmware / hardware versions. These never change
        between polls, so they are fetched ONCE (in _async_setup) and cached
        in `self.info` for the device registry card.
      * get_state -> {"on": bool, "brightness": 0-100, "color": {"temperature": K}}.
        This is the actual poll target, every UPDATE_INTERVAL.
    """

    def __init__(self, hass: HomeAssistant, device: DLightDevice, name: str) -> None:
        """Initialize the coordinator for a single device."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{name} state coordinator",
            update_interval=UPDATE_INTERVAL,
        )
        self.device = device
        # Static identity, filled once by _async_setup before the first poll.
        self.info: dict[str, Any] = {}

    async def _async_setup(self) -> None:
        """Fetch the lamp's static info once, before the first state poll.

        Failure is tolerated: the info payload is cosmetic (device registry
        card), and a lamp that can't answer get_info may still control fine.
        """
        try:
            async with asyncio.timeout(POLL_TIMEOUT):
                info = await self.device.get_info()
        except (TimeoutError, DLightError) as err:
            _LOGGER.warning(
                "Could not read device info for %s (will show generic card): %s",
                self.device.id,
                err,
            )
            return

        if isinstance(info, dict) and info.get("status") == STATUS_SUCCESS:
            # Only the fields the device registry cares about.
            self.info = {
                key: info.get(key) for key in ("swVersion", "hwVersion", "deviceModel")
            }
        else:
            _LOGGER.warning(
                "Device info query for %s returned no usable data: %s",
                self.device.id,
                info,
            )

    async def _async_update_data(self) -> dict[str, Any]:
        """Poll the lamp's current state; any failure marks it unavailable."""
        try:
            async with asyncio.timeout(POLL_TIMEOUT):
                state = await self.device.get_state()
        except TimeoutError as err:
            raise UpdateFailed(f"Timeout polling dLight {self.device.id}") from err
        except DLightError as err:
            raise UpdateFailed(
                f"Error polling dLight {self.device.id}: {err}"
            ) from err

        if not isinstance(state, dict):
            raise UpdateFailed(
                f"Invalid state payload from dLight {self.device.id}: {state!r}"
            )
        return state


class DLightEntity(CoordinatorEntity[DLightCoordinator], LightEntity):
    """A dLight lamp: coordinator data underneath, optimistic guesses on top.

    Every readable property follows the same rule — if we recently sent a
    command, report what we *asked for* (the `_optimistic_*` overrides);
    otherwise report what the coordinator last *confirmed*. A confirmed poll
    (_handle_coordinator_update) clears the guesses.
    """

    _attr_has_entity_name = True  # entity is named after its device...
    _attr_name = None  # ...with no suffix: it IS the device's main feature
    _attr_assumed_state = True  # we guess between polls; HA shows toggle-style UI
    _attr_supported_color_modes = {ColorMode.COLOR_TEMP}
    _attr_color_mode = ColorMode.COLOR_TEMP
    _attr_min_color_temp_kelvin = KELVIN_MIN
    _attr_max_color_temp_kelvin = KELVIN_MAX

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

        # The registry card is built once: coordinator.info is static
        # (fetched a single time at setup, see DLightCoordinator).
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            name=self._base_name,
            manufacturer="dLight (via custom integration)",
            model=coordinator.info.get("deviceModel", "dLight"),
            sw_version=coordinator.info.get("swVersion"),
            hw_version=coordinator.info.get("hwVersion"),
            configuration_url=f"http://{device.ip}",
        )

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

    # --- Commands ---

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on, optionally adjusting brightness and/or color temperature.

        The lamp has no single "apply this state" command, so the needed
        commands are issued concurrently, then the result is assumed
        optimistically rather than waiting up to UPDATE_INTERVAL for a poll.
        """
        brightness: int | None = kwargs.get(ATTR_BRIGHTNESS)
        kelvin: int | None = kwargs.get(ATTR_COLOR_TEMP_KELVIN)

        # HA convention: turn_on with brightness 0 actually means "turn off".
        if brightness is not None and _to_dlight_brightness(brightness) == 0:
            await self.async_turn_off()
            return

        commands = []
        if brightness is not None:
            commands.append(self.device.set_brightness(_to_dlight_brightness(brightness)))
        if kelvin is not None:
            commands.append(self.device.set_color_temperature(int(kelvin)))
        # Setting brightness/temperature implicitly powers the lamp on, so the
        # explicit power command is only needed for a bare turn_on call, or
        # when the lamp is (as far as we know) currently off.
        if not commands or not self.is_on:
            commands.insert(0, self.device.turn_on())

        try:
            await self._send(commands)
        except Exception:  # noqa: BLE001 — never let a flaky lamp break the service call
            _LOGGER.exception("Failed to turn on dLight %s", self.device.id)
            self._clear_optimistic_state()
            self.async_write_ha_state()
            return

        # Commands accepted: predict the outcome. Values not in this call keep
        # their last known state, with sane defaults when nothing is known.
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
        self.async_write_ha_state()

        # Schedule a poll to swap the guess for confirmed state.
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off (optimistically, confirmed by the next poll)."""
        try:
            await self.device.turn_off()
        except Exception:  # noqa: BLE001 — never let a flaky lamp break the service call
            _LOGGER.exception("Failed to turn off dLight %s", self.device.id)
            self._clear_optimistic_state()
            self.async_write_ha_state()
            return

        # Predict "off"; brightness/temperature are meaningless while off.
        self._optimistic_on = False
        self._optimistic_brightness = None
        self._optimistic_kelvin = None
        self.async_write_ha_state()

        await self.coordinator.async_request_refresh()

    async def _send(self, commands: list) -> None:
        """Run device commands concurrently; raise the first failure, if any.

        gather(return_exceptions=True) lets every command finish before we
        judge the batch — a plain gather would abandon in-flight siblings.
        """
        results = await asyncio.gather(*commands, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                raise result

    # --- Coordinator plumbing ---

    @callback
    def _clear_optimistic_state(self) -> None:
        """Drop all pending guesses; properties fall back to coordinator data."""
        self._optimistic_on = None
        self._optimistic_brightness = None
        self._optimistic_kelvin = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """A confirmed poll arrived: real data replaces any optimistic guess."""
        if self.coordinator.data is None:
            return  # failed poll; availability handling is CoordinatorEntity's job
        self._clear_optimistic_state()
        super()._handle_coordinator_update()
