"""Light platform for dLight.

The heavy lifting (device handle, polling) happens in __init__.py and
coordinator.py; this module only defines the entity. DLightEntity is a thin
read-only view over the coordinator's cache, with one twist — *optimistic*
state. Commands (turn on, set brightness, ...) update the entity's state
immediately so the UI feels instant; the next confirmed poll replaces the
guess with the device's reported truth.
"""
from __future__ import annotations

import asyncio
import logging
import math
from typing import Any

from dlightclient import DLightDevice

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, KELVIN_MAX, KELVIN_MIN
from .coordinator import DLightCoordinator

_LOGGER = logging.getLogger(__name__)

# Serialize HA service calls per lamp: rapid UI interactions must not race
# overlapping commands at a single-socket device. Coordinator polling is
# unaffected — this only gates entity commands (turn_on/turn_off).
PARALLEL_UPDATES = 1


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

    # --- Commands ---

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on, optionally adjusting brightness and/or color temperature.

        The lamp has no single "apply this state" command, so the needed
        commands are issued concurrently, then the result is assumed
        optimistically rather than waiting up to a full poll interval.
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
        except Exception as err:
            _LOGGER.exception("Failed to turn on dLight %s", self.device.id)
            self._clear_optimistic_state()
            self.async_write_ha_state()
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="turn_on_failed",
                translation_placeholders={
                    "device_name": self._base_name,
                    "error": str(err),
                },
            ) from err

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
        except Exception as err:
            _LOGGER.exception("Failed to turn off dLight %s", self.device.id)
            self._clear_optimistic_state()
            self.async_write_ha_state()
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="turn_off_failed",
                translation_placeholders={
                    "device_name": self._base_name,
                    "error": str(err),
                },
            ) from err

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
