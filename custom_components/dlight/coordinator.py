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

from dlightclient import STATUS_SUCCESS, DLightDevice, DLightError, discover_devices
from dlightclient.models import DeviceState

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    POLL_INTERVAL,
    POLL_TIMEOUT,
    REDISCOVERY_DURATION,
    REDISCOVERY_FAILURE_THRESHOLD,
)

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
        entry: ConfigEntry,
        device: DLightDevice,
        name: str,
    ) -> None:
        """Initialize the coordinator for a single device."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{name} state coordinator",
            update_interval=timedelta(seconds=POLL_INTERVAL),
        )
        self.device = device
        # Static identity, filled once by _async_setup before the first poll.
        self.info: dict[str, Any] = {}
        # Serializes device *commands* across platforms (light commands,
        # transition fade steps, the identify button's flash sequence): the
        # lamp speaks over a single TCP socket, and PARALLEL_UPDATES only
        # serializes service calls within one platform.
        self.command_lock = asyncio.Lock()
        # Rediscovery bookkeeping: count failed polls in a row, and keep at
        # most one UDP sweep in flight at a time.
        self._consecutive_failures = 0
        self._rediscovery_task: asyncio.Task | None = None

    @callback
    def _handle_device_state_change(
        self,
        device: DLightDevice,
        old_state: DeviceState,
        new_state: DeviceState,
    ) -> None:
        """Handle state change notifications from the device.

        DeviceState is a TypedDict, so new_state is already a plain dict at
        runtime — no conversion is needed before handing it to the coordinator.
        """
        _LOGGER.debug(
            "dLight %s state listener fired: %s -> %s",
            device.id,
            old_state,
            new_state,
        )
        self.async_set_updated_data(new_state)

    async def _async_setup(self) -> None:
        """Fetch the lamp's static info once, before the first state poll.

        Failure is tolerated: the info payload is cosmetic (device registry
        card), and a lamp that can't answer get_info may still control fine.
        """
        try:
            ping_ok = await self.device.ping(timeout=2.0)
        except Exception:  # noqa: BLE001 — defensively catch any errors in ping
            ping_ok = False

        if not ping_ok:
            _LOGGER.warning(
                "Device %s is offline during setup ping check (will show generic card)",
                self.device.id,
            )
            return

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
            self._note_poll_failure()
            raise UpdateFailed(f"Timeout polling dLight {self.device.id}") from err
        except DLightError as err:
            self._note_poll_failure()
            raise UpdateFailed(
                f"Error polling dLight {self.device.id}: {err}"
            ) from err

        if not isinstance(state, dict):
            self._note_poll_failure()
            raise UpdateFailed(
                f"Invalid state payload from dLight {self.device.id}: {state!r}"
            )
        self._consecutive_failures = 0
        return state

    def _note_poll_failure(self) -> None:
        """Count a failed poll; every Nth consecutive failure tries rediscovery.

        The modulo (rather than ==) keeps retrying for as long as the lamp
        stays unreachable — a lamp that changes IP *while* already offline
        would otherwise be missed by a single one-shot sweep.
        """
        self._consecutive_failures += 1
        if self._consecutive_failures % REDISCOVERY_FAILURE_THRESHOLD:
            return
        if self._rediscovery_task is not None and not self._rediscovery_task.done():
            return
        # Tracked (not background) task: it is short-lived, and HA then waits
        # for it on shutdown instead of abandoning a half-done entry update.
        self._rediscovery_task = self.hass.async_create_task(
            self._async_attempt_rediscovery(),
            name=f"dlight-{self.device.id}-rediscovery",
        )

    async def _async_attempt_rediscovery(self) -> None:
        """Sweep the LAN for this lamp and self-heal the entry's stored IP.

        Complements HA's DHCP watcher (manifest `dhcp` matcher): this path
        also works when the lease renewal isn't visible to HA. Finding the
        lamp on a new address updates the config entry and schedules a
        reload, which rebuilds the device handle against the new IP.
        """
        _LOGGER.debug(
            "dLight %s unreachable for %d polls; trying UDP rediscovery",
            self.device.id,
            self._consecutive_failures,
        )
        try:
            ping_ok = await self.device.ping(timeout=2.0)
        except Exception:  # noqa: BLE001 — defensively catch any errors in ping
            ping_ok = False

        if ping_ok:
            _LOGGER.debug(
                "dLight %s is reachable on current IP %s via ping; skipping UDP sweep",
                self.device.id,
                self.device.ip,
            )
            return

        try:
            devices = await discover_devices(discovery_duration=REDISCOVERY_DURATION)
        except Exception:  # noqa: BLE001 — best-effort recovery, never raise
            _LOGGER.debug("dLight rediscovery sweep failed", exc_info=True)
            return

        for found in devices:
            if found.get("deviceId") != self.device.id:
                continue
            new_ip = found.get("ip_address")
            if new_ip and new_ip != self.device.ip:
                _LOGGER.info(
                    "dLight %s found at new address %s (was %s); updating entry",
                    self.device.id,
                    new_ip,
                    self.device.ip,
                )
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={**self.config_entry.data, CONF_IP_ADDRESS: new_ip},
                )
                self.hass.config_entries.async_schedule_reload(
                    self.config_entry.entry_id
                )
            return
