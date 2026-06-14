"""Tests for the dLight sensor platform (brightness and color temperature)."""
from dlightclient import DLightConnectionError

from homeassistant.helpers import entity_registry as er

from custom_components.dlight.const import DOMAIN
from .conftest import setup_integration


async def test_brightness_sensor_initial_value(
    hass, mock_dlight_device, mock_config_entry
):
    """Brightness sensor reports the coordinator's current brightness value."""
    await setup_integration(hass, mock_config_entry)

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, "dlight_test_device_id_brightness"
    )
    assert entity_id is not None

    entry = er.async_get(hass).async_get(entity_id)
    assert entry.entity_category == er.EntityCategory.DIAGNOSTIC

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "50"
    assert state.attributes["unit_of_measurement"] == "%"


async def test_color_temp_sensor_initial_value(
    hass, mock_dlight_device, mock_config_entry
):
    """Color temperature sensor reports the coordinator's current color temp value."""
    await setup_integration(hass, mock_config_entry)

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, "dlight_test_device_id_color_temp"
    )
    assert entity_id is not None

    entry = er.async_get(hass).async_get(entity_id)
    assert entry.entity_category == er.EntityCategory.DIAGNOSTIC

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "4000"
    assert state.attributes["unit_of_measurement"] == "K"


async def test_sensors_update_on_coordinator_refresh(
    hass, mock_dlight_device, mock_config_entry
):
    """Sensor values update when the coordinator polls new state."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    brightness_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, "dlight_test_device_id_brightness"
    )
    color_temp_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, "dlight_test_device_id_color_temp"
    )

    mock_dlight_device.get_state.return_value = {
        "on": True,
        "brightness": 75,
        "color": {"temperature": 3000},
    }
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(brightness_id).state == "75"
    assert hass.states.get(color_temp_id).state == "3000"


async def test_sensors_unavailable_on_coordinator_failure(
    hass, mock_dlight_device, mock_config_entry
):
    """Both sensors go unavailable when the coordinator cannot reach the lamp."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    brightness_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, "dlight_test_device_id_brightness"
    )
    color_temp_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, "dlight_test_device_id_color_temp"
    )

    mock_dlight_device.get_state.side_effect = DLightConnectionError("gone")
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(brightness_id).state == "unavailable"
    assert hass.states.get(color_temp_id).state == "unavailable"

    # Recovery: sensors come back online.
    mock_dlight_device.get_state.side_effect = None
    mock_dlight_device.get_state.return_value = {
        "on": True,
        "brightness": 60,
        "color": {"temperature": 4500},
    }
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(brightness_id).state == "60"
    assert hass.states.get(color_temp_id).state == "4500"
