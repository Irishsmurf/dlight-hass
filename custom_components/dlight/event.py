"""Event platform for dLight: surfaces physical button presses as a device entity.

The detection logic lives entirely in light.py: when a coordinator poll reveals
a state change that was not initiated by Home Assistant, DLightEntity fires the
dlight_physical_control bus event and calls this entity via a direct reference
so it can call _trigger_event() and appear in the UI.

This entity owns no detection logic of its own — it is purely a consumer of
the detection that light.py already performs, expressed as a first-class HA
EventEntity so the interaction is visible in the device page and can be used
as a trigger in the standard event trigger platform.
"""

from __future__ import annotations

import logging

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, EVENT_PHYSICAL_CONTROL

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

EVENT_TYPES = ["turned_on", "turned_off", "changed"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the physical-control event entity for an already-initialized lamp."""
    coordinator = entry.runtime_data
    async_add_entities([DLightEventEntity(coordinator.device, entry)])


class DLightEventEntity(EventEntity):
    """Surfaces physical dLight interactions as a proper HA EventEntity.

    Subscribes to the dlight_physical_control bus event fired by DLightEntity
    (light.py) and calls _trigger_event() so the interaction appears under the
    device in the UI and can be used in standard HA automations.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "physical_control"
    _attr_device_class = EventDeviceClass.BUTTON
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_event_types = EVENT_TYPES

    def __init__(self, device, entry: ConfigEntry) -> None:
        """Initialize the event entity."""
        self._device = device
        self._attr_unique_id = f"dlight_{device.id}_physical_control"
        base_name = entry.title or f"dLight {device.id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)}, name=base_name
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to physical-control bus events when the entity goes live."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.hass.bus.async_listen(
                EVENT_PHYSICAL_CONTROL, self._handle_physical_control
            )
        )

    @callback
    def _handle_physical_control(self, event: Event) -> None:
        """Re-fire a bus event as an EventEntity trigger for this device."""
        if event.data.get("device_id") != self._device.id:
            return
        action = event.data.get("action")
        if action not in self._attr_event_types:
            _LOGGER.debug(
                "dLight %s: ignoring unknown physical control action %r",
                self._device.id,
                action,
            )
            return
        self._trigger_event(action)
        self.async_write_ha_state()
