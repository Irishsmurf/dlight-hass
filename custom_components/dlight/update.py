"""Update platform for dLight: surfaces firmware version via UpdateEntity.

The coordinator fetches swVersion once during setup and caches it in
coordinator.info. The entity surfaces that as `installed_version`; no OTA
source is currently known so `latest_version` is always None.

The entity overrides `available` to stay True whenever swVersion is cached,
even when the lamp is temporarily unreachable. Firmware version is static
metadata — hiding a known fact due to transient connectivity loss is unhelpful.
"""
from __future__ import annotations

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DLightCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[DLightCoordinator],
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the firmware update entity for an initialized lamp."""
    coordinator = entry.runtime_data
    async_add_entities([DLightUpdateEntity(coordinator, entry)])


class DLightUpdateEntity(CoordinatorEntity[DLightCoordinator], UpdateEntity):
    """Surfaces the lamp's installed firmware version.

    latest_version is None because there is no known OTA source yet; this
    makes the entity a passive version display rather than an active updater.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "firmware"
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_latest_version: str | None = None

    def __init__(self, coordinator: DLightCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        device = coordinator.device
        self._attr_unique_id = f"dlight_{device.id}_firmware"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            name=entry.title or f"dLight {device.id}",
        )

    @property
    def available(self) -> bool:
        """Return True when a cached firmware version exists.

        coordinator.info is fetched once at setup and never changes, so
        swVersion remains known even when the lamp is unreachable. Hiding a
        known static fact because of a transient connectivity loss is unhelpful.
        """
        return bool(self.coordinator.info.get("swVersion"))

    @property
    def installed_version(self) -> str | None:
        """Return the firmware version fetched during coordinator setup."""
        return self.coordinator.info.get("swVersion")

    @property
    def latest_version(self) -> str | None:
        """No OTA source configured; always None."""
        return None
