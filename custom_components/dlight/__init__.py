"""The dLight integration.

Lifecycle: async_setup_entry is the composition root — it builds the device
handle and its DLightCoordinator, primes the first refresh, and publishes the
coordinator to platforms via entry.runtime_data (typed as DLightConfigEntry).
Platforms (light.py) only consume; they create nothing.
"""
import logging

from dlightclient import AsyncDLightClient, DLightDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import CONF_DEVICE_ID, PLATFORMS
from .coordinator import DLightCoordinator

_LOGGER = logging.getLogger(__name__)

# The typed alias every signature uses: runtime_data carries the coordinator.
type DLightConfigEntry = ConfigEntry[DLightCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: DLightConfigEntry) -> bool:
    """Set up a dLight lamp from a config entry."""
    ip_address = entry.data.get(CONF_IP_ADDRESS)
    device_id = entry.data.get(CONF_DEVICE_ID)
    if not ip_address or not device_id:
        raise ConfigEntryError(
            f"Config entry {entry.entry_id} is missing IP address or device ID"
        )

    client = AsyncDLightClient(persistent=True)
    # Register close before the first refresh so the connection is always
    # cleaned up — even if async_config_entry_first_refresh raises
    # ConfigEntryNotReady and HA fires the unload hooks during retry teardown.
    entry.async_on_unload(client.close)

    device = DLightDevice(ip_address=ip_address, device_id=device_id, client=client)

    coordinator = DLightCoordinator(
        hass,
        entry,
        device,
        name=entry.title or f"dLight {device_id}",
    )
    # Fetch once before adding entities, so they never appear with unknown
    # state; raises ConfigEntryNotReady (auto-retry) if the lamp is offline.
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Register the push state listener only after a successful first refresh.
    # This avoids a ghost listener on the device object if setup fails and the
    # coordinator is never fully initialised.
    coordinator.device.on_state_change(coordinator._handle_device_state_change)
    entry.async_on_unload(
        lambda: coordinator.device.remove_state_listener(
            coordinator._handle_device_state_change
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DLightConfigEntry) -> bool:
    """Unload a dLight lamp; runtime_data is dropped with the entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
