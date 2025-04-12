"""The dLight integration."""
import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform

# Potentially import constants if you create const.py
# from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# List the platforms that your integration supports.
PLATFORMS = [Platform.LIGHT] # Or use strings: ["light"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up dLight from a config entry."""
    # Store the config entry data (e.g., IP, device ID) in hass.data
    # This assumes you use a Config Flow where entry.data holds the config
    hass.data.setdefault(entry.domain, {})[entry.entry_id] = entry.data

    _LOGGER.info("Setting up dLight entry with data: %s", entry.data)

    # Forward the setup to the light platform.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Forward the unloading to the platforms.
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Clean up hass.data
    if unload_ok:
        hass.data[entry.domain].pop(entry.entry_id)
        if not hass.data[entry.domain]:
            hass.data.pop(entry.domain)

    return unload_ok