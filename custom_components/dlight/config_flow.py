"""Config flow for dLight integration."""
import logging
import voluptuous as vol
from typing import Any
import asyncio # Needed for wait_for and TimeoutError

_LOGGER = logging.getLogger(__name__)

try:
    # Import directly from the installed package
    from dlightclient import (
        AsyncDLightClient,
        DLightDevice, # Although not used directly in flow, good practice to ensure it's available
        DLightError,
        DLightTimeoutError,
        DLightConnectionError,
        DLightResponseError, # Import if needed for more specific error handling
        STATUS_SUCCESS, # Import if needed
        discover_devices,
    )
    _IMPORT_SUCCESS = True
except ImportError:
    _LOGGER.error("dlightclient library not found. Please install requirements.")
    # If setup should fail without the library, raise PlatformNotReady or similar
    # For now, define dummies to allow HA structure loading but prevent setup
    _IMPORT_SUCCESS = False
    class DLightError(Exception): pass
    class DLightTimeoutError(DLightError): pass
    class DLightConnectionError(DLightError): pass
    class DLightResponseError(DLightError): pass
    class AsyncDLightClient: pass
    async def discover_devices(*args, **kwargs): return []
    STATUS_SUCCESS = "SUCCESS"
# --- End Updated Library Imports ---

from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME

from .const import DOMAIN, CONF_DEVICE_ID

_LOGGER = logging.getLogger(__name__)

# Schema for user input form
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): str,
        vol.Required(CONF_DEVICE_ID): str,
        vol.Optional(CONF_NAME): str, # Optional friendly name
    }
)

async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input to ensure connection to the dLight device.

    This function attempts to connect to the dLight device using the provided
    IP address and device ID. It queries the device for its information to
    confirm that the details are correct and the device is reachable.

    Args:
        hass: The Home Assistant instance.
        data: A dictionary containing the user's input, including
              `ip_address`, `device_id`, and an optional `name`.

    Returns:
        A dictionary containing the title for the config entry, which is
        determined from the user-provided name or the device model.

    Raises:
        CannotConnect: If the connection fails, times out, or the device
                       returns an invalid response.
    """
    if not _IMPORT_SUCCESS: # Prevent validation if library failed to import
        raise CannotConnect("dlightclient library not loaded")

    # Use the async client directly for validation query
    # Use a reasonable timeout specific to validation
    client = AsyncDLightClient(default_timeout=5.0)
    ip_address = data[CONF_IP_ADDRESS]
    device_id = data[CONF_DEVICE_ID]
    _LOGGER.debug("Validating connection to %s for device %s", ip_address, device_id)

    try:
        # Call the async query_device_info method
        # Using wait_for is still a good pattern here for explicit timeout control
        info = await asyncio.wait_for(
            client.query_device_info(ip_address, device_id),
            timeout=client.default_timeout
        )

        # Check the response status from the device
        # Check if the device echoed the command (using ResponseError check now)
        # The echo check is now inside the client, raising DLightResponseError
        if not info or info.get("status") != STATUS_SUCCESS:
             _LOGGER.warning("Validation query failed or returned non-SUCCESS: %s", info)
             error_detail = info.get("status", "unknown error") if isinstance(info, dict) else "invalid response"
             raise CannotConnect(f"Device returned non-SUCCESS status: {error_detail}")

        # Successfully connected and got info. Determine title.
        # Prefer user-provided name, fallback to model name, fallback to device ID.
        # Use info.get("deviceModel", device_id) as fallback title part
        model_or_id = info.get("deviceModel") or device_id
        title = data.get(CONF_NAME) or model_or_id # User name > Model > Device ID
        _LOGGER.debug("Validation successful. Title set to: %s", title)
        return {"title": title}

    except asyncio.TimeoutError as err:
        # This catches timeouts from asyncio.wait_for
        _LOGGER.warning("Timeout during validation for %s", ip_address)
        raise CannotConnect(f"Timeout connecting to dLight at {ip_address}") from err
    # Catch specific library errors (ensure imports are correct)
    except DLightTimeoutError as err:
        _LOGGER.warning("Library timeout during validation for %s", ip_address)
        raise CannotConnect(f"Timeout connecting to dLight at {ip_address}") from err
    except DLightConnectionError as err:
         _LOGGER.warning("Connection error during validation for %s: %s", ip_address, err)
         raise CannotConnect(f"Connection error for dLight at {ip_address}: {err}") from err
    except DLightResponseError as err: # Catch response errors (like echo)
         _LOGGER.warning("Response error during validation for %s: %s", ip_address, err)
         raise CannotConnect(f"Invalid response from dLight at {ip_address}: {err}") from err
    except DLightError as err: # Catch other library errors
        _LOGGER.warning("Library error during validation for %s: %s", ip_address, err)
        raise CannotConnect(f"Cannot connect or validate dLight {device_id} at {ip_address}: {err}") from err
    # Catch any other unexpected errors during validation
    except Exception as err:
         _LOGGER.exception("Unexpected exception during validation for %s", ip_address)
         raise CannotConnect(f"Unexpected error validating dLight: {err}") from err


class DLightConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handles the configuration flow for the dLight integration.

    This class manages the user interface for setting up a new dLight device.
    It supports automatic discovery via UDP and manual entry of device details.
    """

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, dict[str, Any]] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step of the user configuration flow.

        If user_input is None, it attempts to discover devices on the network.
        If devices are found, it shows a selection list. Otherwise, it shows
        the manual entry form.
        """
        if user_input is None:
            # Try discovery
            try:
                devices = await discover_devices(discovery_duration=2.0)
                if devices:
                    # Filter out already configured devices
                    current_ids = {
                        entry.unique_id for entry in self._async_current_entries()
                    }
                    self._discovered_devices = {
                        d["deviceId"]: d
                        for d in devices
                        if f"dlight_{d['deviceId']}" not in current_ids
                    }

                    if self._discovered_devices:
                        return await self.async_step_discovery()
            except Exception:
                _LOGGER.exception("Error during device discovery")

            return await self.async_step_manual()

        return await self.async_step_manual(user_input)

    async def async_step_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle selection of a discovered device."""
        if user_input is not None:
            if user_input["selected_device"] == "manual":
                return await self.async_step_manual()

            # Process selected device
            device_id = user_input["selected_device"]
            device = self._discovered_devices[device_id]
            
            user_data = {
                CONF_IP_ADDRESS: device["ip_address"],
                CONF_DEVICE_ID: device_id,
                CONF_NAME: device.get("deviceModel", f"dLight {device_id}"),
            }
            # Proceed to validate and create entry
            return await self.async_step_manual(user_data)

        # Prepare selection list
        device_options = {
            id: f"{d.get('deviceModel', 'dLight')} ({d['ip_address']})"
            for id, d in self._discovered_devices.items()
        }
        device_options["manual"] = "Manually add a device"

        return self.async_show_form(
            step_id="discovery",
            data_schema=vol.Schema(
                {
                    vol.Required("selected_device"): vol.In(device_options),
                }
            ),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual entry of device details."""
        errors: dict[str, str] = {}

        if user_input is not None:
            unique_id = f"dlight_{user_input[CONF_DEVICE_ID]}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception in config flow manual step")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="manual",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

# Define custom exception for config flow validation errors
# This class definition can remain the same
class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect to the dLight device."""
    pass
