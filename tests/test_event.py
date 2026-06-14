"""Tests for the dLight EventEntity (physical control)."""
from homeassistant.helpers import entity_registry as er

from custom_components.dlight.const import DOMAIN, EVENT_PHYSICAL_CONTROL
from .conftest import setup_integration


async def _event_entity_id(hass):
    return er.async_get(hass).async_get_entity_id(
        "event", DOMAIN, "dlight_test_device_id_physical_control"
    )


async def test_event_entity_registered(hass, mock_dlight_device, mock_config_entry):
    """Event entity is registered under the device with diagnostic category."""
    await setup_integration(hass, mock_config_entry)
    entity_id = await _event_entity_id(hass)
    assert entity_id is not None
    entry = er.async_get(hass).async_get(entity_id)
    assert entry.entity_category == er.EntityCategory.DIAGNOSTIC


async def test_event_entity_fires_on_external_off(hass, mock_dlight_device, mock_config_entry):
    """EventEntity fires 'turned_off' when the physical-control bus event arrives."""
    await setup_integration(hass, mock_config_entry)
    entity_id = await _event_entity_id(hass)
    coordinator = mock_config_entry.runtime_data

    mock_dlight_device.get_state.return_value = {
        "on": False,
        "brightness": 0,
        "color": {"temperature": 4000},
    }
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).attributes.get("event_type") == "turned_off"


async def test_event_entity_fires_on_external_on(hass, mock_dlight_device, mock_config_entry):
    """EventEntity fires 'turned_on' when the physical-control bus event arrives."""
    mock_dlight_device.get_state.return_value = {
        "on": False,
        "brightness": 0,
        "color": {"temperature": 4000},
    }
    await setup_integration(hass, mock_config_entry)
    entity_id = await _event_entity_id(hass)
    coordinator = mock_config_entry.runtime_data

    mock_dlight_device.get_state.return_value = {
        "on": True,
        "brightness": 80,
        "color": {"temperature": 4000},
    }
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).attributes.get("event_type") == "turned_on"


async def test_event_entity_fires_on_brightness_change(hass, mock_dlight_device, mock_config_entry):
    """EventEntity fires 'changed' when brightness changes externally."""
    await setup_integration(hass, mock_config_entry)
    entity_id = await _event_entity_id(hass)
    coordinator = mock_config_entry.runtime_data

    mock_dlight_device.get_state.return_value = {
        "on": True,
        "brightness": 80,
        "color": {"temperature": 4000},
    }
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).attributes.get("event_type") == "changed"


async def test_event_entity_not_updated_when_state_unchanged(hass, mock_dlight_device, mock_config_entry):
    """EventEntity stays idle when the polled state is identical to the baseline."""
    await setup_integration(hass, mock_config_entry)
    entity_id = await _event_entity_id(hass)
    coordinator = mock_config_entry.runtime_data

    # Same state as the initial fixture (on=True, brightness=50, temp=4000).
    mock_dlight_device.get_state.return_value = {
        "on": True,
        "brightness": 50,
        "color": {"temperature": 4000},
    }
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).attributes.get("event_type") is None


async def test_event_entity_ignores_other_device(hass, mock_dlight_device, mock_config_entry):
    """EventEntity ignores physical-control bus events for a different device ID."""
    await setup_integration(hass, mock_config_entry)
    entity_id = await _event_entity_id(hass)

    # Fire a bus event for a different device.
    hass.bus.async_fire(
        EVENT_PHYSICAL_CONTROL,
        {
            "device_id": "some_other_device",
            "entity_id": "light.other",
            "action": "turned_off",
            "previous_state": {},
            "new_state": {},
        },
    )
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).attributes.get("event_type") is None


async def test_event_entity_not_fired_on_first_poll(hass, mock_dlight_device, mock_config_entry):
    """No event fires during integration setup (the initial poll sets the baseline)."""
    from unittest.mock import patch

    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = await _event_entity_id(hass)
    assert hass.states.get(entity_id).attributes.get("event_type") is None
