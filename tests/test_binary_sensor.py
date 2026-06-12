"""Tests for the dLight connectivity binary sensor."""
from dlightclient import DLightConnectionError

from homeassistant.helpers import entity_registry as er

from custom_components.dlight.const import DOMAIN
from .conftest import setup_integration


async def test_connectivity_sensor_tracks_poll_health(
    hass, mock_dlight_device, mock_config_entry
):
    """The sensor reports on/off with poll health and never goes unavailable."""
    await setup_integration(hass, mock_config_entry)

    entity_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor", DOMAIN, "dlight_test_device_id_connectivity"
    )
    assert entity_id is not None
    registry_entry = er.async_get(hass).async_get(entity_id)
    assert registry_entry.entity_category == er.EntityCategory.DIAGNOSTIC

    assert hass.states.get(entity_id).state == "on"

    # Lamp drops off the network: the light goes unavailable, but the
    # connectivity sensor must stay available and flip to "off" — that
    # failure is precisely the data it reports.
    mock_dlight_device.get_state.side_effect = DLightConnectionError("gone")
    coordinator = mock_config_entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("light.test_light").state == "unavailable"
    assert hass.states.get(entity_id).state == "off"

    # Lamp comes back: sensor returns to "on".
    mock_dlight_device.get_state.side_effect = None
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "on"
