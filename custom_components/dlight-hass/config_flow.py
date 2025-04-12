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
    STATUS_SUCCESS = "SUCCESS"
# --- End Updated Library Imports ---

from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME

DOMAIN = "dlight-hass"

_LOGGER = logging.getLogger(__name__)

# Define constants for config flow keys used in this file
CONF_DEVICE_ID = "device_id"

# Schema for user input form
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): str,
        vol.Required(CONF_DEVICE_ID): str,
        vol.Optional(CONF_NAME): str, # Optional friendly name
    }
)

async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """
    Validate the user input allows us to connect to the device.

    Args:
        hass: Home Assistant instance.
        data: Dictionary of user input (ip_address, device_id, name).

    Returns:
        Dictionary with title for the config entry on success.

    Raises:
        CannotConnect: If connection or validation fails.
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
    """Handle a config flow for dLight."""

    VERSION = 1
    # Optional: Add connection class if relevant
    # CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user initiation or form submission."""
        errors: dict[str, str] = {}

        # Runs when user submits the form
        if user_input is not None:
            # Set unique ID based on device ID to prevent duplicates
            unique_id = f"dlight_{user_input[CONF_DEVICE_ID]}"
            await self.async_set_unique_id(unique_id)
            # Check if a config entry with this unique ID already exists
            self._abort_if_unique_id_configured(updates=user_input)

            try:
                # Validate the user's input by trying to connect/query
                info = await validate_input(self.hass, user_input)

                # Input is valid, create the config entry
                _LOGGER.info("Creating config entry for %s with data %s", info['title'], user_input)
                return self.async_create_entry(title=info["title"], data=user_input)

            except CannotConnect as e:
                # Specific error indicating connection/validation failure
                # Use the error message from the exception if desired, or keep generic
                errors["base"] = "cannot_connect"
                _LOGGER.warning("Validation failed: %s", e)
            except Exception:  # Catch unforeseen errors during validation/creation
                _LOGGER.exception("Unexpected exception in config flow user step")
                errors["base"] = "unknown"

        # Show the form if it's the first step or if errors occurred
        # Add suggested values from previous input if form is reshown due to error
        return self.async_show_form(
            step_id="user",
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
