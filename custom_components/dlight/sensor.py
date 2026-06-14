"""Sensor platform for dLight: brightness (%) and color temperature (K).

Both sensors are backed by the shared coordinator — no extra polling.
They go unavailable when the coordinator has no data (lamp offline).
"""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
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
    """Add brightness and color-temperature sensors for an initialized lamp."""
    coordinator = entry.runtime_data
    async_add_entities([
        DLightBrightnessSensor(coordinator, entry),
        DLightColorTempSensor(coordinator, entry),
    ])


class _DLightSensorBase(CoordinatorEntity[DLightCoordinator], SensorEntity):
    """Shared base for both dLight sensor entities."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: DLightCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        device = coordinator.device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            name=entry.title or f"dLight {device.id}",
        )

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.coordinator.data is not None


class DLightBrightnessSensor(_DLightSensorBase):
    """Reports lamp brightness as a percentage (0–100)."""

    _attr_translation_key = "brightness"
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator: DLightCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"dlight_{coordinator.device.id}_brightness"

    @property
    def native_value(self) -> int | None:
        data = self.coordinator.data
        if not data:
            return None
        return data.get("brightness")


class DLightColorTempSensor(_DLightSensorBase):
    """Reports lamp color temperature in Kelvin."""

    _attr_translation_key = "color_temp"
    _attr_native_unit_of_measurement = UnitOfTemperature.KELVIN

    def __init__(self, coordinator: DLightCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"dlight_{coordinator.device.id}_color_temp"

    @property
    def native_value(self) -> int | None:
        data = self.coordinator.data
        if not data:
            return None
        color = data.get("color")
        if not isinstance(color, dict):
            return None
        return color.get("temperature")
