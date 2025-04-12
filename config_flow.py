"""Config flow for dLight integration."""
import logging
import voluptuous as vol
from typing import Any

# Import your library and exceptions
try:
    from dlightclient.dlight import DLightClient, DLightError, DLightTimeoutError, DLightConnectionError
except ImportError:
    from .dlightclient.dlight import DLightClient, DLightError, DLightTimeoutError, DLightConnectionError

from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult # Use FlowResult for type hinting

# Potentially import constants
# from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Schema for user input form
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("ip_address"): str,
        vol.Required("device_id"): str,
        vol.Optional("name"): str, # Optional friendly name
    }
)

async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    client = DLightClient()
    ip_address = data["ip_address"]
    device_id = data["device_id"]

    try:
        # Run blocking query_device_info in executor to test connection/ID
        info = await hass.async_add_executor_job(
            client.query_device_info, ip_address, device_id
        )
        # You could add more checks here based on the info if needed
        if not info or info.get("status") != "SUCCESS":
            raise CannotConnect("Failed to get valid info from device.")

        # Return info that you want to store in the config entry.
        # Use device_id as title unless name is provided
        title = data.get("name") or info.get("deviceModel", device_id) # Use model or ID as title fallback
        return {"title": title}

    except DLightTimeoutError as err:
        raise CannotConnect(f"Timeout connecting to dLight at {ip_address}") from err
    except DLightConnectionError as err:
        raise CannotConnect(f"Connection error for dLight at {ip_address}: {err}") from err
    except DLightError as err:
        raise CannotConnect(f"Cannot connect to dLight {device_id} at {ip_address}: {err}") from err
    except Exception as err:
        _LOGGER.exception("Unexpected exception during validation") # Log full trace
        raise CannotConnect(f"Unexpected error validating dLight: {err}") from err


class DLightConfigFlow(config_entries.ConfigFlow, domain="dlight_hass"): # Use your domain
    """Handle a config flow for dLight."""

    VERSION = 1
    # Optional: Allow only a single configuration flow instance at a time.
    # CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # Avoid duplicate entries based on device_id
            await self.async_set_unique_id(f"dlight_{user_input['device_id']}")
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
                # Input is valid, create the config entry
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception in config flow")
                errors["base"] = "unknown"

        # If there is no user input or there were errors, show the form again.
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

# Define custom exception for config flow
class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""