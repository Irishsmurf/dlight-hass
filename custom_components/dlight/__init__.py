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
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from .const import CONF_DEVICE_ID, DOMAIN, PLATFORMS
from .coordinator import DLightCoordinator

_LOGGER = logging.getLogger(__name__)

# The typed alias every signature uses: runtime_data carries the coordinator.
type DLightConfigEntry = ConfigEntry[DLightCoordinator]

SERVICE_FLASH = "flash"


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
    # HA's _async_process_on_unload schedules any returned coroutine as a task,
    # so passing client.close (an async method) directly is correct.
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

    # Register the dlight.flash service once; idempotent across multi-lamp setups.
    if not hass.services.has_service(DOMAIN, SERVICE_FLASH):
        async def _handle_flash(call: ServiceCall) -> None:
            target_device_id: str | None = call.data.get("device_id")
            if not target_device_id:
                return
            dev_reg = dr.async_get(hass)
            device_entry = dev_reg.async_get(target_device_id)
            if not device_entry:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="flash_unknown_device",
                    translation_placeholders={"device_id": target_device_id},
                )
            for entry_id in device_entry.config_entries:
                cfg = hass.config_entries.async_get_entry(entry_id)
                if cfg and cfg.domain == DOMAIN and cfg.runtime_data is not None:
                    coord = cfg.runtime_data
                    coord.identify_in_progress = True
                    try:
                        async with coord.command_lock:
                            await coord.device.flash()
                    finally:
                        coord.identify_in_progress = False
                    return
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="flash_unknown_device",
                translation_placeholders={"device_id": target_device_id},
            )

        hass.services.async_register(DOMAIN, SERVICE_FLASH, _handle_flash)

    def _maybe_remove_service() -> None:
        remaining = [
            e for e in hass.config_entries.async_entries(DOMAIN)
            if e.entry_id != entry.entry_id
        ]
        if not remaining and hass.services.has_service(DOMAIN, SERVICE_FLASH):
            hass.services.async_remove(DOMAIN, SERVICE_FLASH)

    entry.async_on_unload(_maybe_remove_service)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DLightConfigEntry) -> bool:
    """Unload a dLight lamp; runtime_data is dropped with the entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
