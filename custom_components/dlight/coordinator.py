"""Data update coordinator for dLight lamps.

Lives in its own module so any platform (light today; sensor/update tomorrow)
can share one coordinator per lamp. Created by __init__.async_setup_entry and
published to platforms via entry.runtime_data.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from dlightclient import STATUS_SUCCESS, DLightDevice, DLightError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import POLL_INTERVAL, POLL_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class DLightCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Owns all communication with one lamp.

    Two payloads, two cadences:
      * get_info  -> model / firmware / hardware versions. These never change
        between polls, so they are fetched ONCE (in _async_setup) and cached
        in `self.info` for the device registry card.
      * get_state -> {"on": bool, "brightness": 0-100, "color": {"temperature": K}}.
        This is the actual poll target, every poll_interval seconds.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        device: DLightDevice,
        name: str,
    ) -> None:
        """Initialize the coordinator for a single device."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{name} state coordinator",
            update_interval=timedelta(seconds=POLL_INTERVAL),
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
                key: info.get(key)
                for key in ("swVersion", "hwVersion", "deviceModel", "macAddress")
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
                # force_update bypasses DLightDevice's local state cache.
                # Since dlight-client 1.5.0 that cache is written optimistically
                # by command methods (before the lamp confirms), so a plain
                # get_state() would echo our own guesses back instead of
                # polling — and a dead lamp would never raise here.
                state = await self.device.get_state(force_update=True)
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
