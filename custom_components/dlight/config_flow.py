"""Config flow for dLight: discover lamps via UDP broadcast, or add manually.

Flow map::

    user step ──(lamps found)──> discovery step ──(pick a lamp)──┐
        │                              │ ("manual" option)       │
        └──(none found / error)──> manual step <─────────────────┘
                                       │
                          validate_input() probes the lamp
                                       │
                                 create entry

Two extra paths keep entries pointing at the right IP after DHCP changes:
the user step silently heals known lamps rediscovered on a new address, and
async_step_reconfigure lets the user edit a lamp's details from the UI.
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from dlightclient import (
    STATUS_SUCCESS,
    AsyncDLightClient,
    DLightError,
    discover_devices_stream,
)

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import device_registry as dr

if TYPE_CHECKING:
    # Import for typing only: pulling in the dhcp component at runtime would
    # drag its requirements (aiodhcpwatcher etc.) into environments that
    # never use DHCP discovery, like the test suite.
    from homeassistant.components.dhcp import DhcpServiceInfo

from .const import (
    CONF_DEVICE_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): str,
        vol.Required(CONF_DEVICE_ID): str,
        vol.Optional(CONF_NAME): str,  # optional friendly name
    }
)

# How long discovery listens for lamps, and how long validation waits.
DISCOVERY_DURATION = 2.0
VALIDATION_TIMEOUT = 5.0


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Probe the lamp once to prove the IP/device-id combination works.

    Returns {"title": ...} for the new entry, preferring the user's chosen
    name, then the model the device reports, then the raw device id.

    Raises CannotConnect for *any* failure — the form only has one error slot,
    so every root cause funnels into one exception type (chained via ``from``
    so the log still shows the real reason).
    """
    client = AsyncDLightClient(default_timeout=VALIDATION_TIMEOUT)
    ip_address = data[CONF_IP_ADDRESS]
    device_id = data[CONF_DEVICE_ID]
    _LOGGER.debug("Validating connection to %s for device %s", ip_address, device_id)

    try:
        # wait_for is belt-and-braces on top of the client's own timeout.
        info = await asyncio.wait_for(
            client.query_device_info(ip_address, device_id),
            timeout=VALIDATION_TIMEOUT,
        )
    except (TimeoutError, DLightError) as err:
        raise CannotConnect(
            f"Cannot reach dLight {device_id} at {ip_address}: {err}"
        ) from err
    except Exception as err:
        _LOGGER.exception("Unexpected error validating dLight at %s", ip_address)
        raise CannotConnect(f"Unexpected error validating dLight: {err}") from err

    if not isinstance(info, dict) or info.get("status") != STATUS_SUCCESS:
        raise CannotConnect(f"dLight returned a non-SUCCESS response: {info}")

    return {"title": data.get(CONF_NAME) or info.get("deviceModel") or device_id}


class DLightConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """UI flow: try network discovery first, fall back to a manual form."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow with an empty discovery cache."""
        self._discovered: dict[str, dict[str, Any]] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Entry point: scan the LAN and offer a pick-list if lamps respond."""
        if user_input is not None:
            return await self.async_step_manual(user_input)

        devices: list[dict] = []
        try:
            async for found in discover_devices_stream(timeout=DISCOVERY_DURATION):
                devices.append(found)
        except Exception:  # noqa: BLE001 — discovery is best-effort, never fatal
            _LOGGER.exception("dLight discovery failed; falling back to manual entry")

        _LOGGER.debug("dLight discovery found %d device(s)", len(devices))
        self._discovered = self._filter_new_devices(devices)
        self._heal_known_lamps(devices)

        if self._discovered:
            return await self.async_step_discovery()
        return await self.async_step_discovery_none()

    def _filter_new_devices(self, devices: list[dict]) -> dict[str, dict]:
        """Return only devices not already registered as config entries."""
        known_ids = {entry.unique_id for entry in self._async_current_entries() if entry.unique_id}
        return {
            device_id: d
            for d in devices
            if (device_id := d.get("deviceId")) and f"dlight_{device_id}" not in known_ids
        }

    def _heal_known_lamps(self, devices: list[dict]) -> None:
        """Update the stored IP for any known lamp found on a new address."""
        known = {entry.unique_id: entry for entry in self._async_current_entries()}
        for found in devices:
            entry = known.get(f"dlight_{found['deviceId']}")
            if entry is not None and entry.data.get(CONF_IP_ADDRESS) != found["ip_address"]:
                _LOGGER.info(
                    "dLight %s moved to %s; updating its config entry",
                    found["deviceId"],
                    found["ip_address"],
                )
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_IP_ADDRESS: found["ip_address"]}
                )
                # Reload so the running coordinator targets the new address.
                self.hass.config_entries.async_schedule_reload(entry.entry_id)

    async def async_step_discovery_none(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Inform the user that no lamps were found and offer next steps."""
        return self.async_show_menu(
            step_id="discovery_none",
            menu_options=["manual", "retry"],
        )

    async def async_step_retry(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Retry discovery without triggering IP self-healing for existing lamps.

        The user clicked "Try again" to scan for *new* lamps, not to heal
        existing entries — silently reloading a coordinator mid-use is an
        unexpected side effect in this context.
        """
        devices: list[dict] = []
        try:
            async for found in discover_devices_stream(timeout=DISCOVERY_DURATION):
                devices.append(found)
        except Exception:  # noqa: BLE001 — discovery is best-effort, never fatal
            _LOGGER.exception("dLight discovery failed during retry; falling back to discovery_none")

        _LOGGER.debug("dLight retry discovery found %d device(s)", len(devices))
        self._discovered = self._filter_new_devices(devices)

        if self._discovered:
            return await self.async_step_discovery()
        return await self.async_step_discovery_none()

    async def async_step_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Let the user pick a discovered lamp (or opt out to manual entry)."""
        if user_input is not None:
            choice = user_input["selected_device"]
            if choice == "manual":
                return await self.async_step_manual()

            device = self._discovered[choice]
            # Pre-fill the manual step; it owns validation and entry creation.
            return await self.async_step_manual(
                {
                    CONF_IP_ADDRESS: device["ip_address"],
                    CONF_DEVICE_ID: choice,
                    CONF_NAME: device.get("deviceModel", f"dLight {choice}"),
                }
            )

        options = {
            device_id: f"{info.get('deviceModel', 'dLight')} ({info['ip_address']})"
            for device_id, info in self._discovered.items()
        }
        options["manual"] = "Manually add a device"

        return self.async_show_form(
            step_id="discovery",
            data_schema=vol.Schema({vol.Required("selected_device"): vol.In(options)}),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Validate device details (typed or pre-filled) and create the entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # One entry per physical lamp, keyed by device id. Re-adding a
            # known lamp aborts, but heals its stored IP as a side effect.
            await self.async_set_unique_id(f"dlight_{user_input[CONF_DEVICE_ID]}")
            self._abort_if_unique_id_configured(
                updates={CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS]}
            )

            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error in dLight manual step")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        # First visit, or validation failed: (re)show the form. Suggested
        # values keep whatever the user (or discovery) already filled in.
        return self.async_show_form(
            step_id="manual",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_dhcp(self, discovery_info: DhcpServiceInfo) -> FlowResult:
        """A known lamp renewed its DHCP lease: self-heal its stored IP.

        The manifest matcher is `registered_devices` only, so this fires just
        for MAC addresses already in the device registry. DHCP traffic has no
        dLight device id, so the chain is MAC -> registry device -> our
        identifier; the standard unique-id machinery then updates the entry's
        IP (and reloads it) before aborting.
        """
        _LOGGER.debug("dLight DHCP step triggered (mac=<redacted>)")
        mac = dr.format_mac(discovery_info.macaddress)
        device = dr.async_get(self.hass).async_get_device(
            connections={(dr.CONNECTION_NETWORK_MAC, mac)}
        )
        if device is not None:
            device_id = next(
                (id_ for domain, id_ in device.identifiers if domain == DOMAIN),
                None,
            )
            if device_id is not None:
                await self.async_set_unique_id(f"dlight_{device_id}")
                self._abort_if_unique_id_configured(
                    updates={CONF_IP_ADDRESS: discovery_info.ip}
                )
        return self.async_abort(reason="unknown_device")

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Let the user fix a lamp's details — typically a changed IP address."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            # Reconfigure must keep pointing at the same physical lamp; a
            # different device id means the user wants a new entry instead.
            await self.async_set_unique_id(f"dlight_{user_input[CONF_DEVICE_ID]}")
            self._abort_if_unique_id_mismatch()

            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error in dLight reconfigure step")
                errors["base"] = "unknown"
            else:
                # Persist the new details and restart the entry against them.
                return self.async_update_reload_and_abort(
                    entry, title=info["title"], data=user_input
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or entry.data
            ),
            errors=errors,
        )


class CannotConnect(exceptions.HomeAssistantError):
    """The lamp could not be reached, or rejected the validation probe."""
