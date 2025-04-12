"""Platform for dLight lights."""
import logging
from typing import Any
import math # For brightness conversion
import datetime # For coordinator updates
import async_timeout # For coordinator updates
import asyncio # For potential delays and timeout errors

# Import your library and exceptions
try:
    # Assuming library installed via requirements
    from dlightclient.dlight import AsyncDLightClient, DLightError, DLightTimeoutError
except ImportError:
    # Fallback if library is vendored (copied into the integration folder)
    from .dlightclient.dlight import AsyncDLightClient, DLightError, DLightTimeoutError


from homeassistant.components.light import (
    LightEntity,
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ColorMode # Use enum member directly
    # REMOVED deprecated imports: SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)


# Potentially import constants
# from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

# Define update interval for polling
UPDATE_INTERVAL = datetime.timedelta(seconds=30) # Example: Poll every 30 seconds

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up dLight light based on a config entry."""
    # Get config data stored in __init__.py
    config_data = hass.data[entry.domain][entry.entry_id]
    target_ip = config_data.get("ip_address")
    device_id = config_data.get("device_id")
    # Get name from config entry (set during config flow) or create default
    name = entry.title or f"dLight {device_id}"

    if not target_ip or not device_id:
        _LOGGER.error("Missing IP address or Device ID in config entry: %s", entry.entry_id)
        return

    # Create an instance of your async client library
    client = AsyncDLightClient()

    # --- Coordinator for polling ---
    async def async_update_data():
        """Fetch data from API endpoint."""
        _LOGGER.debug("Polling dLight state for %s", name)
        try:
            # Use the async version of the client library
            async with async_timeout.timeout(10): # Timeout for the update operation
                # No need for executor job with async library
                state_data = await client.query_device_state(target_ip, device_id)

                if not state_data or state_data.get("status") != "SUCCESS":
                    raise UpdateFailed(f"Failed to query device state: {state_data}")
                # Return only the 'states' dict if present
                if "states" not in state_data:
                     raise UpdateFailed(f"Invalid state data received: {state_data}")
                return state_data["states"]
        except asyncio.TimeoutError as err: # Catch asyncio timeout specifically
            raise UpdateFailed(f"Timeout communicating with dLight {device_id} ({name}): {err}") from err
        except DLightTimeoutError as err: # Catch library's specific timeout
            raise UpdateFailed(f"Timeout communicating with dLight {device_id} ({name}): {err}") from err
        except DLightError as err: # Catch other library errors
            raise UpdateFailed(f"Error communicating with dLight {device_id} ({name}): {err}") from err
        except Exception as err: # Catch unexpected errors
             _LOGGER.exception("Unexpected error updating dLight %s", name)
             raise UpdateFailed(f"Unexpected error updating dLight {device_id} ({name}): {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{name} state",
        update_method=async_update_data,
        update_interval=UPDATE_INTERVAL,
    )

    # Fetch initial data so we have states before entity is added
    await coordinator.async_config_entry_first_refresh()

    # Create the entity and add it to Home Assistant
    async_add_entities([DLightEntity(coordinator, client, entry, name, target_ip, device_id)])


class DLightEntity(CoordinatorEntity, LightEntity):
    """Representation of a dLight Light."""

    _attr_has_entity_name = True # Use device name + entity name ("Light")
    _attr_assumed_state = True # Enable optimistic mode

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        client: AsyncDLightClient, # Use async client type hint
        entry: ConfigEntry,
        name: str,
        ip_address: str,
        device_id: str,
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator) # Pass coordinator to CoordinatorEntity
        self.client = client
        self.entry = entry
        self._ip_address = ip_address
        self._device_id = device_id
        # Use entry.title as the base device name if available
        self._base_name = entry.title or name

        # --- Basic Entity Attributes ---
        # Unique ID based on device ID provided during setup
        self._attr_unique_id = f"dlight_{self._device_id}"

        # --- Internal state attributes for optimistic mode ---
        # Initialize with None, they will be updated by coordinator or service calls
        self._attr_is_on = None
        self._attr_brightness = None
        self._attr_color_temp_kelvin = None

        # --- Light Specific Attributes ---
        # Supported features based on API: Brightness and Color Temp
        self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
        # Start with COLOR_TEMP as the default mode if supported
        self._attr_color_mode = ColorMode.COLOR_TEMP
        # Get Kelvin range from docs (or query device info if possible)
        self._attr_min_color_temp_kelvin = 2600
        self._attr_max_color_temp_kelvin = 6000

        # Device Info for grouping entities
        # Link entity to HA device registry
        self._attr_device_info = DeviceInfo(
            identifiers={(entry.domain, self._device_id)}, # Use domain and unique ID
            name=self._base_name, # Use name from config entry title
            manufacturer="Google (via custom integration)", # Or unknown
            # Model/SW/HW could be fetched from query_device_info if desired
            # Example: Fetching from initial coordinator data (might not always be available)
            # model=self.coordinator.data.get("model", "dLight") if self.coordinator.data else "dLight",
            # sw_version=self.coordinator.data.get("swVersion") if self.coordinator.data else None,
            # hw_version=self.coordinator.data.get("hwVersion") if self.coordinator.data else None,
            configuration_url=f"http://{self._ip_address}", # Basic link
            # Link to config entry for diagnostics/options
            # entry_type=config_entries.SOURCE_REAUTH, # Or SOURCE_USER if appropriate
            # via_device=(entry.domain, "hub_or_bridge_id") # If discovery was via another device
        )

    # name property is now handled by setting _attr_has_entity_name = True
    # and HA using device name + entity description (default "Light")

    # --- State Properties ---
    # These read data fetched by the coordinator OR from optimistic updates

    @property
    def available(self) -> bool:
        """Return True if entity is available (coordinator has data)."""
        # Availability based on coordinator success
        return super().available and self.coordinator.last_update_success

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        # Return optimistic state if available, otherwise coordinator data
        if self._attr_is_on is not None: # Check internal optimistic state first
             return self._attr_is_on
        if self.coordinator.data:
            return self.coordinator.data.get("on")
        return None # Unknown state if coordinator hasn't fetched data

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        # Return optimistic state if available, otherwise coordinator data
        if self._attr_brightness is not None:
             return self._attr_brightness
        if self.coordinator.data:
            dlight_brightness = self.coordinator.data.get("brightness")
            if dlight_brightness is not None:
                # Convert dLight brightness (0-100) to HA brightness (0-255)
                return math.ceil((dlight_brightness / 100) * 255)
        return None

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the CT color value in Kelvin."""
         # Return optimistic state if available, otherwise coordinator data
        if self._attr_color_temp_kelvin is not None:
             return self._attr_color_temp_kelvin
        # Check coordinator data exists and 'color' key is present
        if self.coordinator.data and isinstance(self.coordinator.data.get("color"), dict):
            return self.coordinator.data["color"].get("temperature")
        return None

    # --- Service Call Handlers ---

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        brightness_ha = kwargs.get(ATTR_BRIGHTNESS)
        color_temp_k = kwargs.get(ATTR_COLOR_TEMP_KELVIN)

        # Store optimistic state updates locally before writing
        optimistic_on = True # Assume turn_on means ON
        optimistic_brightness = self.brightness # Start with current value
        optimistic_color_temp = self.color_temp_kelvin # Start with current value

        try:
            # Determine target brightness/temp for optimistic update
            if brightness_ha is not None:
                optimistic_brightness = brightness_ha
            if color_temp_k is not None:
                optimistic_color_temp = int(color_temp_k)

            # --- Send Commands to Device ---
            # If only 'turn_on' is called (no kwargs), send explicit 'on'.
            if not kwargs:
                 _LOGGER.debug("Turning on %s (explicit call)", self.entity_id)
                 await self.client.set_light_state(self._ip_address, self._device_id, True)
                 # Keep previous brightness/temp for optimistic state if just turning on

            # Set Color Temp (if provided) - Send before brightness? Order might matter.
            if color_temp_k is not None:
                 _LOGGER.debug("Setting %s color temp to %d K", self.entity_id, optimistic_color_temp)
                 await self.client.set_color_temperature(self._ip_address, self._device_id, optimistic_color_temp)
                 # await asyncio.sleep(0.1) # Optional delay

            # Set Brightness (if provided)
            if brightness_ha is not None:
                # Convert HA brightness (0-255) to dLight brightness (0-100)
                dlight_brightness = max(0, min(100, math.ceil((optimistic_brightness / 255) * 100)))
                _LOGGER.debug("Setting %s brightness to %d%% (%d HA)", self.entity_id, dlight_brightness, optimistic_brightness)
                # Only send if brightness > 0, otherwise it acts like turn_off
                if dlight_brightness > 0:
                     await self.client.set_brightness(self._ip_address, self._device_id, dlight_brightness)
                else:
                    # If brightness 0 is requested via turn_on service, treat as turn_off
                    _LOGGER.debug("Brightness 0 requested via turn_on, calling turn_off instead")
                    await self.async_turn_off() # Call the turn_off logic
                    return # Exit turn_on logic

            # ---- Optimistic Update ----
            self._attr_is_on = optimistic_on
            self._attr_brightness = optimistic_brightness
            self._attr_color_temp_kelvin = optimistic_color_temp
            # Handle defaults if turning on from unknown state
            if self._attr_brightness is None: self._attr_brightness = 255
            if self._attr_color_temp_kelvin is None: self._attr_color_temp_kelvin = self._attr_min_color_temp_kelvin

            self.async_write_ha_state() # Update HA state immediately
            # --------------------------

            # Ask coordinator to refresh state later to confirm
            # Use schedule_update_ha_state=False as we already updated optimistically
            await self.coordinator.async_request_refresh()

        except (DLightError, ValueError) as err:
            _LOGGER.error("Error controlling dLight %s: %s", self.entity_id, err)
            # Clear optimistic state on error? Or let coordinator fix it?
            # Let's clear it to avoid showing wrong state if command failed.
            self._attr_is_on = None
            self._attr_brightness = None
            self._attr_color_temp_kelvin = None
            self.async_write_ha_state() # Write the cleared state
        except Exception as err:
             _LOGGER.exception("Unexpected error turning on dLight %s", self.entity_id)
             # Clear optimistic state
             self._attr_is_on = None
             self._attr_brightness = None
             self._attr_color_temp_kelvin = None
             self.async_write_ha_state()


    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        try:
            _LOGGER.debug("Turning off %s", self.entity_id)
            await self.client.set_light_state(self._ip_address, self._device_id, False)

            # ---- Optimistic Update ----
            self._attr_is_on = False
            # Brightness/Color irrelevant when off, clear optimistic values
            self._attr_brightness = None
            self._attr_color_temp_kelvin = None
            self.async_write_ha_state()
            # --------------------------

            # Ask coordinator to refresh state later to confirm
            # Use schedule_update_ha_state=False as we already updated optimistically
            await self.coordinator.async_request_refresh()
        except DLightError as err:
            _LOGGER.error("Error turning off dLight %s: %s", self.entity_id, err)
            # Clear optimistic state
            self._attr_is_on = None
            self._attr_brightness = None
            self._attr_color_temp_kelvin = None
            self.async_write_ha_state()
        except Exception as err:
             _LOGGER.exception("Unexpected error turning off dLight %s", self.entity_id)
             # Clear optimistic state
             self._attr_is_on = None
             self._attr_brightness = None
             self._attr_color_temp_kelvin = None
             self.async_write_ha_state()

    # update method is handled by CoordinatorEntity via coordinator.async_update_data

    # This method is called by the coordinator after a successful poll
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data is None:
            # Don't update if coordinator failed last poll
            return

        # Clear optimistic state attributes now that we have confirmed data
        self._attr_is_on = None
        self._attr_brightness = None
        self._attr_color_temp_kelvin = None

        # Let the CoordinatorEntity handle updating the state from coordinator.data
        super()._handle_coordinator_update()