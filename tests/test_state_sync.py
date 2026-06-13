"""Tests for the dLight state change listener integration."""
from homeassistant.core import HomeAssistant
from .conftest import setup_integration


async def test_listener_registration_on_setup(
    hass: HomeAssistant, mock_dlight_device, mock_config_entry
):
    """Test that the state change listener is registered on setup."""
    await setup_integration(hass, mock_config_entry)
    mock_dlight_device.on_state_change.assert_called_once()


async def test_listener_unregistration_on_unload(
    hass: HomeAssistant, mock_dlight_device, mock_config_entry
):
    """Test that the state change listener is removed when the config entry is unloaded."""
    await setup_integration(hass, mock_config_entry)

    # Unload the config entry
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_dlight_device.remove_state_listener.assert_called_once()


async def test_listener_propagates_state_change(
    hass: HomeAssistant, mock_dlight_device, mock_config_entry
):
    """Test that state changes from the listener update the coordinator and entity state."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    # Initially, brightness is 50% = 128 HA scale
    state = hass.states.get("light.test_light")
    assert state.state == "on"
    assert state.attributes.get("brightness") == 128

    # Simulate a listener event from the device (e.g. brightness set to 80%)
    old_state = {"on": True, "brightness": 50, "color": {"temperature": 4000}}
    new_state = {"on": True, "brightness": 80, "color": {"temperature": 4000}}

    # Call the listener callbacks
    for cb in mock_dlight_device._state_callbacks:
        cb(mock_dlight_device, old_state, new_state)
    await hass.async_block_till_done()

    # The coordinator data should be updated
    assert coordinator.data == new_state

    # The entity state should be updated to 204 (80% of 255)
    state = hass.states.get("light.test_light")
    assert state.state == "on"
    assert state.attributes.get("brightness") == 204
