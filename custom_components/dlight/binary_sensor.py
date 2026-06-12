"""Binary sensor platform for dLight: a connectivity diagnostic.

Mirrors the coordinator's poll health as an on/off signal. Unlike the light
entity — which goes *unavailable* when polls fail — this sensor stays
available and reports "disconnected", so automations can react to a lamp
dropping off the network (notify, retry, power-cycle a smart plug, ...).
"""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DLightCoordinator

# Read-only view over coordinator data; nothing to serialize.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[DLightCoordinator],
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the connectivity sensor for an already-initialized lamp."""
    coordinator = entry.runtime_data
    async_add_entities([DLightConnectivitySensor(coordinator, entry)])


class DLightConnectivitySensor(CoordinatorEntity[DLightCoordinator], BinarySensorEntity):
    """Reports whether the last poll reached the lamp."""

    _attr_has_entity_name = True  # named by device class: "<device> Connectivity"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: DLightCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor from the shared coordinator."""
        super().__init__(coordinator)
        device = coordinator.device
        self._attr_unique_id = f"dlight_{device.id}_connectivity"
        # The light entity owns the full registry card; identifiers attach
        # this sensor to the same device. The name is repeated because
        # platform setup order is alphabetical — without it, this platform
        # (first alphabetically) would create the device nameless and entity
        # IDs would come out as "binary_sensor.none_connectivity".
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            name=entry.title or f"dLight {device.id}",
        )

    @property
    def available(self) -> bool:
        """Always available: a failed poll is this sensor's *data*, not an outage.

        CoordinatorEntity would otherwise flip the sensor to unavailable on
        the very event it exists to report.
        """
        return True

    @property
    def is_on(self) -> bool:
        """Return True while polls are reaching the lamp."""
        return self.coordinator.last_update_success
