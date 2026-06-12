"""Tests for the dLight identify button."""
import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from custom_components.dlight.const import DOMAIN
from .conftest import setup_integration


async def _get_button_entity_id(hass) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        "button", DOMAIN, "dlight_test_device_id_identify"
    )
    assert entity_id is not None
    return entity_id


async def test_identify_button_flashes_lamp(hass, mock_dlight_device, mock_config_entry):
    """Pressing identify runs the device's flash sequence."""
    await setup_integration(hass, mock_config_entry)
    entity_id = await _get_button_entity_id(hass)

    # Diagnostic entity, attached to the same device as the light.
    registry_entry = er.async_get(hass).async_get(entity_id)
    assert registry_entry.entity_category == er.EntityCategory.DIAGNOSTIC

    await hass.services.async_call(
        "button", "press", {"entity_id": entity_id}, blocking=True
    )
    mock_dlight_device.flash.assert_awaited_once()


async def test_identify_button_failure_raises(hass, mock_dlight_device, mock_config_entry):
    """A flash sequence that does not complete surfaces as a service error."""
    await setup_integration(hass, mock_config_entry)
    entity_id = await _get_button_entity_id(hass)

    mock_dlight_device.flash.return_value = False
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button", "press", {"entity_id": entity_id}, blocking=True
        )

    mock_dlight_device.flash.side_effect = Exception("socket torn")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button", "press", {"entity_id": entity_id}, blocking=True
        )
