"""Tests for the dLight update (firmware) entity."""
from dlightclient import DLightConnectionError

from homeassistant.helpers import entity_registry as er

from custom_components.dlight.const import DOMAIN
from .conftest import setup_integration


async def test_firmware_entity_installed_version(
    hass, mock_dlight_device, mock_config_entry
):
    """Update entity reports the swVersion fetched during coordinator setup."""
    await setup_integration(hass, mock_config_entry)

    entity_id = er.async_get(hass).async_get_entity_id(
        "update", DOMAIN, "dlight_test_device_id_firmware"
    )
    assert entity_id is not None

    entry = er.async_get(hass).async_get(entity_id)
    assert entry.entity_category == er.EntityCategory.DIAGNOSTIC

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes.get("installed_version") == "1.0.0"


async def test_firmware_entity_latest_version_is_none(
    hass, mock_dlight_device, mock_config_entry
):
    """latest_version is None because no OTA source is configured."""
    await setup_integration(hass, mock_config_entry)

    entity_id = er.async_get(hass).async_get_entity_id(
        "update", DOMAIN, "dlight_test_device_id_firmware"
    )
    state = hass.states.get(entity_id)
    assert state.attributes.get("latest_version") is None


async def test_firmware_entity_unavailable_on_coordinator_failure(
    hass, mock_dlight_device, mock_config_entry
):
    """Firmware entity goes unavailable when the coordinator loses the lamp."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    entity_id = er.async_get(hass).async_get_entity_id(
        "update", DOMAIN, "dlight_test_device_id_firmware"
    )

    assert hass.states.get(entity_id).state != "unavailable"

    mock_dlight_device.get_state.side_effect = DLightConnectionError("gone")
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "unavailable"

    # Recovery: entity becomes available again.
    mock_dlight_device.get_state.side_effect = None
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state != "unavailable"
    assert hass.states.get(entity_id).attributes.get("installed_version") == "1.0.0"
