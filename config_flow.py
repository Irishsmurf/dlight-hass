"""Config flow for dLight integration."""
import logging
import voluptuous as vol
from typing import Any
import asyncio # Needed for wait_for and TimeoutError

# Import your async library and exceptions
try:
    # Assuming library installed via requirements
    from dlightclient.dlight import AsyncDLightClient, DLightError, DLightTimeoutError, DLightConnectionError
except ImportError:
    # Fallback if library is vendored
    # Ensure this path matches your structure if vendoring
    from .dlightclient.dlight import AsyncDLightClient, DLightError, DLightTimeoutError, DLightConnectionError

from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME

# Potentially import constants
# from .const import DOMAIN # DOMAIN would typically be "dlight"

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
        hass: Home Assistant instance (not directly used here but passed by HA).
        data: Dictionary of user input (ip_address, device_id, name).

    Returns:
        Dictionary with title for the config entry on success.

    Raises:
        CannotConnect: If connection or validation fails.
    """
    # Use the async client
    client = AsyncDLightClient(default_timeout=5.0) # Use a reasonable timeout for validation
    ip_address = data[CONF_IP_ADDRESS]
    device_id = data[CONF_DEVICE_ID]
    _LOGGER.debug("Validating connection to %s for device %s", ip_address, device_id)

    try:
        # Call the async query_device_info method using asyncio.wait_for for timeout
        info = await asyncio.wait_for(
            client.query_device_info(ip_address, device_id),
            timeout=client.default_timeout # Use timeout from client instance
        )

        # Check the response status from the device
        if not info or info.get("status") != "SUCCESS":
             _LOGGER.warning("Validation query failed or returned non-SUCCESS: %s", info)
             # Provide more specific error if possible based on response
             error_detail = info.get("status", "unknown error") if isinstance(info, dict) else "invalid response"
             raise CannotConnect(f"Device returned non-SUCCESS status: {error_detail}")

        # Successfully connected and got info. Determine title.
        # Prefer user-provided name, fallback to model name, fallback to device ID.
        title = data.get(CONF_NAME) or info.get("deviceModel", device_id)
        _LOGGER.debug("Validation successful. Title set to: %s", title)
        return {"title": title}

    except asyncio.TimeoutError as err:
        # This catches timeouts from asyncio.wait_for
        _LOGGER.warning("Timeout during validation for %s", ip_address)
        raise CannotConnect(f"Timeout connecting to dLight at {ip_address}") from err
    # Catch specific library errors
    except DLightTimeoutError as err:
        _LOGGER.warning("Library timeout during validation for %s", ip_address)
        raise CannotConnect(f"Timeout connecting to dLight at {ip_address}") from err
    except DLightConnectionError as err:
         _LOGGER.warning("Connection error during validation for %s: %s", ip_address, err)
         raise CannotConnect(f"Connection error for dLight at {ip_address}: {err}") from err
    except DLightError as err: # Catch other library errors
        _LOGGER.warning("Library error during validation for %s: %s", ip_address, err)
        raise CannotConnect(f"Cannot connect or validate dLight {device_id} at {ip_address}: {err}") from err
    # Catch any other unexpected errors during validation
    except Exception as err:
         _LOGGER.exception("Unexpected exception during validation for %s", ip_address)
         raise CannotConnect(f"Unexpected error validating dLight: {err}") from err


class DLightConfigFlow(config_entries.ConfigFlow, domain="dlight"): # Ensure domain matches!
    """Handle a config flow for dLight."""

    VERSION = 1
    # Optional: Use if the integration communicates with devices that require polling.
    # CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user initiation or form submission."""
        errors: dict[str, str] = {}

        # Runs when user submits the form
        if user_input is not None:
            # Set unique ID based on device ID to prevent duplicates
            # Using a prefix helps ensure uniqueness across integrations
            unique_id = f"dlight_{user_input[CONF_DEVICE_ID]}"
            await self.async_set_unique_id(unique_id)
            # Check if a config entry with this unique ID already exists
            # Allow reconfiguration using the same flow if needed (check HA docs for reauth flows)
            self._abort_if_unique_id_configured(updates=user_input)

            try:
                # Validate the user's input by trying to connect/query
                info = await validate_input(self.hass, user_input)

                # Input is valid, create the config entry
                _LOGGER.info("Creating config entry for %s", info['title'])
                return self.async_create_entry(title=info["title"], data=user_input)

            except CannotConnect:
                # Specific error indicating connection/validation failure
                errors["base"] = "cannot_connect"
                _LOGGER.warning("Validation failed: Cannot connect")
            except Exception:  # Catch unforeseen errors during validation/creation
                _LOGGER.exception("Unexpected exception in config flow user step")
                errors["base"] = "unknown"

        # Show the form if it's the first step or if errors occurred
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

# Define custom exception for config flow validation errors
class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect to the dLight device."""

