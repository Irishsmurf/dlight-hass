"""Button platform for dLight: an Identify button.

Pressing it runs the client library's flash() helper — the lamp blinks a few
times and is restored to its previous state — so a user with several lamps
can tell which physical device belongs to which entry.
"""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DLightCoordinator

_LOGGER = logging.getLogger(__name__)

# Identify is a multi-second command sequence; never run two at once.
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[DLightCoordinator],
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the identify button for an already-initialized lamp."""
    coordinator = entry.runtime_data
    async_add_entities([DLightIdentifyButton(coordinator, entry)])


class DLightIdentifyButton(CoordinatorEntity[DLightCoordinator], ButtonEntity):
    """Blink the lamp so the user can match the entity to the hardware."""

    _attr_has_entity_name = True  # named by device class: "<device> Identify"
    _attr_device_class = ButtonDeviceClass.IDENTIFY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: DLightCoordinator, entry: ConfigEntry) -> None:
        """Initialize the button from the shared coordinator."""
        super().__init__(coordinator)
        device = coordinator.device
        self._attr_unique_id = f"dlight_{device.id}_identify"
        self._base_name = entry.title or f"dLight {device.id}"
        # The light entity owns the full registry card; identifiers attach
        # this button to the same device. The name is repeated because
        # platform setup order is alphabetical — without it, a platform
        # registering before light.py would create the device nameless and
        # entity IDs would come out as "button.none_identify".
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)}, name=self._base_name
        )

    async def async_press(self) -> None:
        """Flash the lamp; hold the command lock for the whole sequence.

        flash() saves state, blinks, and restores — a fade step or light
        command landing mid-sequence would corrupt the state it restores,
        so the lock spans the entire run, not individual commands.
        """
        device = self.coordinator.device
        try:
            async with self.coordinator.command_lock:
                success = await device.flash()
        except Exception as err:
            _LOGGER.exception("Identify flash failed for dLight %s", device.id)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="identify_failed",
                translation_placeholders={
                    "device_name": self._base_name,
                    "error": str(err),
                },
            ) from err
        if not success:
            # flash() swallows device errors and reports via its bool result.
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="identify_failed",
                translation_placeholders={
                    "device_name": self._base_name,
                    "error": "flash sequence did not complete",
                },
            )
