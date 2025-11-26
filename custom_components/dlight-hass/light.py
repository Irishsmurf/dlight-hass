"""Platform for dLight lights using dlightclient library."""
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.light import (
    LightEntity,
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ColorMode,
    ENTITY_ID_FORMAT  # Used for default entity_id generation if needed
)
import logging
from typing import Any, Dict, Optional
import math  # For brightness conversion
import datetime  # For coordinator updates
import async_timeout  # For coordinator updates
import asyncio  # For potential delays and timeout errors

_LOGGER = logging.getLogger(__name__)

# Import the refactored library components
try:
    from dlightclient import (
        AsyncDLightClient,
        DLightDevice,
        DLightError,
        DLightTimeoutError,
        DLightConnectionError,
        STATUS_SUCCESS
    )
    # Import constants if needed, e.g., for Kelvin range defaults
    # from dlightclient import constants
except ImportError:
    # Handle case where library isn't installed (should not happen in HA)
    _LOGGER.error("dlightclient library not found. Please install it.")

# Define update interval for polling
UPDATE_INTERVAL = datetime.timedelta(
    seconds=30)  # Example: Poll every 30 seconds


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the dLight light platform from a config entry.

    This function is called by Home Assistant to set up the light platform.
    It retrieves the configuration from the config entry, creates a
    coordinator for data polling, initializes the `DLightEntity`, and adds
    it to Home Assistant.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry for this platform.
        async_add_entities: A callback function for adding entities.
    """
    # Get config data stored during config flow (likely in entry.data)
    # config_data = hass.data[entry.domain][entry.entry_id] # This might not be needed if data is in entry.data
    target_ip = entry.data.get("ip_address")
    device_id = entry.data.get("device_id")
    # Get name from config entry (set during config flow) or create default
    name = entry.title or f"dLight {device_id}"

    if not target_ip or not device_id:
        _LOGGER.error(
            "Missing IP address or Device ID in config entry data: %s", entry.entry_id)
        return
    # If each device needs its own client (unlikely here), create inside coordinator/entity
    client = AsyncDLightClient()
    # Create the DLightDevice instance to represent this specific light
    device = DLightDevice(ip_address=target_ip,
                          device_id=device_id, client=client)
    _LOGGER.info("Setting up dLight device: %s", device)

    # --- Coordinator for polling ---

    async def async_update_data() -> Dict[str, Any]:
        """Fetch data from the dLight device using the DLightDevice instance."""
        _LOGGER.debug("Polling dLight state for %s (%s)", name, device_id)

        # Use the DLightDevice methods for fetching data
        try:
            # Fetch state and info concurrently
            # Timeout for the entire update operation
            async with async_timeout.timeout(10):
                results = await asyncio.gather(
                    device.get_state(),  # Use device method
                    device.get_info(),  # Use device method
                    return_exceptions=True
                )
                state_result = results[0]
                info_result = results[1]

                combined_data: Dict[str, Any] = {}

                # Process state result
                if isinstance(state_result, DLightError):
                    _LOGGER.warning(
                        "Failed to query device state for %s: %s", name, state_result)
                    # Allow update to proceed if info is okay, otherwise fail
                    if not isinstance(info_result, dict):  # Check if info also failed
                        raise UpdateFailed(
                            f"Failed to query essential state for {name}: {state_result}") from state_result
                    # state_data remains empty
                elif isinstance(state_result, Exception):
                    _LOGGER.error(
                        "Unexpected error querying state for %s: %s", name, state_result, exc_info=True)
                    if not isinstance(info_result, dict):
                        raise UpdateFailed(
                            f'Unexpected error querying state for {name}: {state_result}') from state_result
                    # state_data remains empty
                elif not isinstance(state_result, dict):
                    # get_state should return a dict, even if empty
                    _LOGGER.warning(
                        "Invalid state data type received for %s: %s", name, type(state_result))
                    if not isinstance(info_result, dict):
                        raise UpdateFailed(
                            f"Invalid state data received for {name}")
                    # state_data remains empty
                else:
                    # Successfully got state data (already extracted by device.get_state)
                    combined_data.update(state_result)

                # Process info result
                if isinstance(info_result, DLightError):
                    _LOGGER.warning(
                        "Failed to query device info for %s: %s", name, info_result)
                    # Don't fail update just because info failed, but log it
                elif isinstance(info_result, Exception):
                    _LOGGER.error(
                        "Unexpected error querying info for %s: %s", name, info_result, exc_info=True)
                elif not isinstance(info_result, dict):
                    _LOGGER.warning(
                        "Invalid info data type received for %s: %s", name, type(info_result))
                # Check status if present
                elif info_result.get("status") == STATUS_SUCCESS:
                    # Extract relevant info fields if needed for device registry etc.
                    combined_data.update({
                        "swVersion": info_result.get("swVersion"),
                        "hwVersion": info_result.get("hwVersion"),
                        "deviceModel": info_result.get("deviceModel"),
                    })
                else:
                    _LOGGER.warning(
                        "Non-SUCCESS info data received for %s: %s", name, info_result)

                # Check if we got *any* useful data
                if not combined_data or ("on" not in combined_data and "swVersion" not in combined_data):
                    # Raise UpdateFailed only if both state and info seem completely invalid/missing
                    _LOGGER.warning(
                        "Failed to get any valid data from device %s, state=%s, info=%s", name, state_result, info_result)
                    # Re-raise original error if state failed critically
                    if isinstance(state_result, DLightError):
                        raise UpdateFailed(f"No valid data") from state_result
                    if isinstance(info_result, DLightError):
                        raise UpdateFailed(f"No valid data") from info_result
                    raise UpdateFailed(
                        f"Failed to get any valid data from device {name}")

                _LOGGER.debug(
                    "Coordinator update successful for %s. Data: %s", name, combined_data)
                return combined_data

        except asyncio.TimeoutError as err:  # Catch asyncio timeout specifically
            raise UpdateFailed(
                f"Timeout communicating with dLight {device_id} ({name}): {err}") from err
        # Catch specific library errors
        except (DLightTimeoutError, DLightConnectionError) as err:
            raise UpdateFailed(
                f"Network error communicating with dLight {device_id} ({name}): {err}") from err
        except DLightError as err:  # Catch other library errors
            raise UpdateFailed(
                f"Error communicating with dLight {device_id} ({name}): {err}") from err
        except Exception as err:  # Catch unexpected errors during update logic
            _LOGGER.exception("Unexpected error updating dLight %s", name)
            raise UpdateFailed(
                f"Unexpected error updating dLight {device_id} ({name}): {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{name} state coordinator",  # More specific name
        update_method=async_update_data,
        update_interval=UPDATE_INTERVAL,
    )

    # Fetch initial data so we have states before entity is added
    await coordinator.async_config_entry_first_refresh()

    # Create the entity and add it to Home Assistant
    # Pass the DLightDevice instance instead of client/ip/id
    async_add_entities([DLightEntity(coordinator, device, entry)])


class DLightEntity(CoordinatorEntity[DataUpdateCoordinator[Dict[str, Any]]], LightEntity):
    """Represents a dLight light entity.

    This entity is responsible for communicating with a single dLight device.
    It uses a `DataUpdateCoordinator` to periodically poll the device for its
    state and provides methods for controlling the light (turn on/off, set
    brightness, etc.). The entity also supports optimistic updates for a
    responsive user experience.
    """

    _attr_has_entity_name = True  # Use device name + entity name ("Light")
    # Optimistic mode assumes commands succeed instantly and updates the state locally
    # Set to False if you prefer to wait for the next coordinator poll to confirm state
    _attr_assumed_state = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: DLightDevice,  # Accept DLightDevice instance
        entry: ConfigEntry,  # Keep entry for unique_id/device_info linkage
    ) -> None:
        """Initialize the dLight entity.

        Args:
            coordinator: The data update coordinator for this entity.
            device: The `DLightDevice` instance for this light.
            entry: The config entry associated with this entity.
        """
        super().__init__(coordinator)  # Pass coordinator to CoordinatorEntity
        self.device = device  # Store the DLightDevice instance
        self.entry = entry
        # Use device properties for attributes
        self._base_name = entry.title or f"dLight {self.device.id}"

        # --- Basic Entity Attributes ---
        # Unique ID based on device ID
        self._attr_unique_id = f"dlight_{self.device.id}"

        # --- Internal state attributes for optimistic mode ---
        self._optimistic_on: Optional[bool] = None
        # Store HA brightness (0-255)
        self._optimistic_brightness: Optional[int] = None
        self._optimistic_color_temp: Optional[int] = None

        # --- Light Specific Attributes ---
        self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
        self._attr_color_mode = ColorMode.COLOR_TEMP
        # Get Kelvin range from docs or device info if available
        self._attr_min_color_temp_kelvin = 2600
        self._attr_max_color_temp_kelvin = 6000

        # Device Info - build using device properties and coordinator data
        self._update_device_info()  # Call helper to set initial device info

    @callback
    def _update_device_info(self) -> None:
        """Update the DeviceInfo for the entity.

        This method populates the `device_info` attribute with data from the
        coordinator, such as model, software version, and hardware version.
        This information is then displayed in the Home Assistant UI.
        """
        # Use coordinator data for model/sw/hw as it's polled
        device_info_data = self.coordinator.data or {}
        self._attr_device_info = DeviceInfo(
            # Use domain and device ID
            identifiers={(self.entry.domain, self.device.id)},
            name=self._base_name,  # Use name from config entry title or default
            manufacturer="dLight (via custom integration)",
            model=device_info_data.get("deviceModel", "dLight"),
            sw_version=device_info_data.get("swVersion"),
            hw_version=device_info_data.get("hwVersion"),
            configuration_url=f"http://{self.device.ip}",  # Use device IP
        )

    # --- State Properties ---

    @property
    def available(self) -> bool:
        """Return True if the entity is available.

        The availability is determined by the success of the last coordinator
        update. If the coordinator fails to poll the device, this property
        will return False.

        Returns:
            True if the entity is available, False otherwise.
        """
        # Availability based on coordinator success
        # Let CoordinatorEntity handle the base availability check
        return super().available  # This checks coordinator.last_update_success

    @property
    def is_on(self) -> bool | None:
        """Return the current on/off state of the light.

        This property returns the optimistic state if available, otherwise it
        falls back to the state reported by the coordinator.

        Returns:
            True if the light is on, False if it is off, or None if the
            state is unknown.
        """
        # Return optimistic state if available, otherwise coordinator data
        if self._optimistic_on is not None:
            return self._optimistic_on
        if self.coordinator.data:
            return self.coordinator.data.get("on")
        return None  # Unknown state

    @property
    def brightness(self) -> int | None:
        """Return the current brightness of the light.

        The brightness is scaled from the dLight's 0-100 range to Home
        Assistant's 0-255 range. This property returns the optimistic state
        if available, otherwise it falls back to the state reported by the
        coordinator.

        Returns:
            The brightness of the light (0-255), or None if the state is
            unknown.
        """
        # Return optimistic state if available, otherwise coordinator data
        if self._optimistic_brightness is not None:
            return self._optimistic_brightness
        if self.coordinator.data:
            dlight_brightness = self.coordinator.data.get("brightness")
            if dlight_brightness is not None:
                # Convert dLight brightness (0-100) to HA brightness (0-255)
                return math.ceil((dlight_brightness / 100) * 255)
        return None

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the current color temperature of the light in Kelvin.

        This property returns the optimistic state if available, otherwise it
        falls back to the state reported by the coordinator.

        Returns:
            The color temperature of the light in Kelvin, or None if the
            state is unknown.
        """
        # Return optimistic state if available, otherwise coordinator data
        if self._optimistic_color_temp is not None:
            return self._optimistic_color_temp
        # Check coordinator data exists and 'color' key is present
        if self.coordinator.data and isinstance(self.coordinator.data.get("color"), dict):
            return self.coordinator.data["color"].get("temperature")
        return None

    # --- Service Call Handlers ---

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on.

        This method sends the necessary command(s) to the dLight device to
        turn it on. It can also handle setting the brightness and color
        temperature at the same time. An optimistic state is set immediately
        for a responsive UI.

        Args:
            **kwargs: A dictionary of additional arguments, such as
                      `ATTR_BRIGHTNESS` and `ATTR_COLOR_TEMP_KELVIN`.
        """
        brightness_ha = kwargs.get(ATTR_BRIGHTNESS)  # HA brightness 0-255
        color_temp_k = kwargs.get(ATTR_COLOR_TEMP_KELVIN)

        # Store optimistic state updates locally before writing
        optimistic_on = True
        # Start with current known state for brightness/temp if not provided in call
        optimistic_brightness = brightness_ha if brightness_ha is not None else self.brightness
        optimistic_color_temp = color_temp_k if color_temp_k is not None else self.color_temp_kelvin

        try:
            # --- Send Commands using DLightDevice ---
            tasks = []
            dlight_brightness = None

            # Handle Brightness Conversion and Command
            if brightness_ha is not None:
                # Convert HA brightness (0-255) to dLight brightness (0-100)
                dlight_brightness = max(
                    0, min(100, math.ceil((brightness_ha / 255) * 100)))
                if dlight_brightness > 0:
                    _LOGGER.debug("Device %s: Queuing set_brightness to %d%% (%d HA)",
                                  self.device.id, dlight_brightness, brightness_ha)
                    tasks.append(self.device.set_brightness(dlight_brightness))
                else:
                    # Brightness 0 means turn off
                    _LOGGER.debug(
                        "Device %s: Brightness 0 requested, calling turn_off", self.device.id)
                    await self.async_turn_off()
                    return  # Exit turn_on logic

            # Handle Color Temp Command
            if color_temp_k is not None:
                _LOGGER.debug(
                    "Device %s: Queuing set_color_temperature to %d K", self.device.id, color_temp_k)
                tasks.append(
                    self.device.set_color_temperature(int(color_temp_k)))

            # Handle Turn On Command
            # Only send explicit 'turn_on' if no brightness/color temp change is also requested,
            # as setting brightness > 0 or color temp implicitly turns the light on.
            # Or always send turn_on first? Let's try sending it if needed.
            # If brightness or color temp is being set, the light will turn on.
            # If only turn_on is called (no kwargs), we need to send it.
            # If the light is currently off and brightness/temp is changing, it will turn on.
            # If the light is already on, sending turn_on again is likely harmless.
            # Let's send turn_on if no other commands are queued or if it's explicitly called.
            if not tasks:
                _LOGGER.debug(
                    "Device %s: Queuing turn_on (explicit call)", self.device.id)
                tasks.append(self.device.turn_on())
            elif not self.is_on:  # If currently off, ensure it turns on
                _LOGGER.debug(
                    "Device %s: Queuing turn_on (implicit via brightness/temp)", self.device.id)
                tasks.insert(0, self.device.turn_on())  # Add turn_on first

            # Execute commands concurrently
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                # Check for errors in results
                for i, res in enumerate(results):
                    if isinstance(res, Exception):
                        _LOGGER.error(
                            "Device %s: Error during turn_on sequence (task %d): %s", self.device.id, i, res)
                        # Raise the first encountered error
                        raise res

            # ---- Optimistic Update ----
            self._optimistic_on = optimistic_on
            self._optimistic_brightness = optimistic_brightness
            self._optimistic_color_temp = optimistic_color_temp
            # Handle defaults if turning on from unknown state
            if self._optimistic_brightness is None:
                self._optimistic_brightness = 255  # Default to full?
            if self._optimistic_color_temp is None:
                self._optimistic_color_temp = self._attr_min_color_temp_kelvin  # Default to min?

            self.async_write_ha_state()  # Update HA state immediately
            # --------------------------

            # Ask coordinator to refresh state later to confirm
            await self.coordinator.async_request_refresh()

        except (DLightError, ValueError) as err:
            _LOGGER.error("Error controlling dLight %s: %s",
                          self.device.id, err)
            # Clear optimistic state on error
            self._clear_optimistic_state()
            self.async_write_ha_state()  # Write the cleared state
        except Exception as err:
            _LOGGER.exception(
                "Unexpected error turning on dLight %s", self.device.id)
            self._clear_optimistic_state()
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off.

        This method sends the command to the dLight device to turn it off.
        An optimistic state is set immediately for a responsive UI.

        Args:
            **kwargs: A dictionary of additional arguments (not used).
        """
        try:
            _LOGGER.debug("Device %s: Turning off", self.device.id)
            await self.device.turn_off()  # Use device method

            # ---- Optimistic Update ----
            self._optimistic_on = False
            # Brightness/Color irrelevant when off, clear optimistic values
            self._optimistic_brightness = None
            self._optimistic_color_temp = None
            self.async_write_ha_state()
            # --------------------------

            # Ask coordinator to refresh state later to confirm
            await self.coordinator.async_request_refresh()
        except DLightError as err:
            _LOGGER.error("Error turning off dLight %s: %s",
                          self.device.id, err)
            self._clear_optimistic_state()
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.exception(
                "Unexpected error turning off dLight %s", self.device.id)
            self._clear_optimistic_state()
            self.async_write_ha_state()

    @callback
    def _clear_optimistic_state(self) -> None:
        """Clear the internal optimistic state variables.

        This is called when the coordinator provides a new, confirmed state
        or when an error occurs during a service call.
        """
        self._optimistic_on = None
        self._optimistic_brightness = None
        self._optimistic_color_temp = None

    # This method is called by the coordinator after a successful poll
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator.

        This method is called by the `CoordinatorEntity` base class when the
        coordinator successfully fetches new data. It clears the optimistic
        state, updates the device info, and triggers a state update for the
        entity.
        """
        if self.coordinator.data is None:
            # Don't update if coordinator failed last poll
            _LOGGER.debug(
                "Coordinator update skipped for %s, data is None", self.device.id)
            return

        _LOGGER.debug("Handling coordinator update for %s", self.device.id)
        # Clear optimistic state attributes now that we have confirmed data
        self._clear_optimistic_state()

        # Update device info based on potentially new data from coordinator
        self._update_device_info()

        # Let the CoordinatorEntity handle applying the polled state
        # to the entity's attributes (_attr_is_on etc. via the properties)
        super()._handle_coordinator_update()
