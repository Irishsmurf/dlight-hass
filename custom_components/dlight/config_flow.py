"""Config flow for dLight: discover lamps via UDP broadcast, or add manually.

Flow map::

    user step ──(lamps found)──> discovery step ──(pick a lamp)──┐
        │                              │ ("manual" option)       │
        └──(none found / error)──> manual step <─────────────────┘
                                       │
                          validate_input() probes the lamp
                                       │
                                 create entry
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from dlightclient import (
    STATUS_SUCCESS,
    AsyncDLightClient,
    DLightError,
    discover_devices,
)

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_DEVICE_ID, DOMAIN

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

        try:
            devices = await discover_devices(discovery_duration=DISCOVERY_DURATION)
        except Exception:  # noqa: BLE001 — discovery is best-effort, never fatal
            _LOGGER.exception("dLight discovery failed; falling back to manual entry")
            devices = []

        # Hide lamps that already have a config entry (matched by unique_id).
        known = {entry.unique_id for entry in self._async_current_entries()}
        self._discovered = {
            d["deviceId"]: d for d in devices if f"dlight_{d['deviceId']}" not in known
        }

        if self._discovered:
            return await self.async_step_discovery()
        return await self.async_step_manual()

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
            # One entry per physical lamp, keyed by device id.
            await self.async_set_unique_id(f"dlight_{user_input[CONF_DEVICE_ID]}")
            self._abort_if_unique_id_configured()

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


class CannotConnect(exceptions.HomeAssistantError):
    """The lamp could not be reached, or rejected the validation probe."""
