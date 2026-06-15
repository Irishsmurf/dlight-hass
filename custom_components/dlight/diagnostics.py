"""Diagnostics support for dLight.

Lets users attach a sanitized snapshot to bug reports (Settings -> Devices &
Services -> dLight -> Download diagnostics) instead of hand-collecting logs.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant

from . import DLightConfigEntry
from .const import CONF_DEVICE_ID

# Anything that identifies the user's network or specific device.
TO_REDACT = {CONF_IP_ADDRESS, CONF_DEVICE_ID, "macAddress"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DLightConfigEntry
) -> dict[str, Any]:
    """Return a redacted snapshot of the entry and its coordinator."""
    coordinator = entry.runtime_data
    last_success = coordinator.last_successful_poll
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "device_info": async_redact_data(coordinator.info or {}, TO_REDACT),
        "state": coordinator.data,  # last polled on/brightness/color
        "last_update_success": coordinator.last_update_success,
        "update_interval": str(coordinator.update_interval),
        "coordinator_health": {
            "consecutive_failures": coordinator.consecutive_failures,
            "last_success": last_success.isoformat() if last_success else None,
            "rediscovery_in_flight": coordinator.rediscovery_in_progress,
        },
    }
