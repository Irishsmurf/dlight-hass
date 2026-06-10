"""The dLight integration.

Lifecycle: Home Assistant calls async_setup_entry once per configured lamp,
which forwards setup to the light platform (light.py). The light platform
builds the polling coordinator and stores it in hass.data[DOMAIN][entry_id];
async_unload_entry reverses both steps.
"""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a dLight lamp from a config entry."""
    # Reserve our domain's slot; light.py fills it with this entry's coordinator.
    hass.data.setdefault(DOMAIN, {})
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a dLight lamp and drop its coordinator."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    return unload_ok
