import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dlight.const import DOMAIN, UPDATE_INTERVAL, CONF_DEVICE_ID

@pytest.fixture
def mock_dlight_device():
    """Mock a dLight device."""
    with patch("custom_components.dlight.light.DLightDevice", autospec=True) as mock_device_class:
        mock_device = mock_device_class.return_value
        mock_device.id = "test_device_id"
        mock_device.ip = "127.0.0.1"
        mock_device.get_state = AsyncMock(return_value={"on": True, "brightness": 50, "color": {"temperature": 4000}})
        mock_device.get_info = AsyncMock(return_value={
            "status": "SUCCESS",
            "swVersion": "1.0.0",
            "hwVersion": "1.0.0",
            "deviceModel": "Test Lamp"
        })
        mock_device.turn_on = AsyncMock()
        mock_device.turn_off = AsyncMock()
        mock_device.set_brightness = AsyncMock()
        mock_device.set_color_temperature = AsyncMock()
        yield mock_device

from datetime import timedelta
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_DEVICE_ID: "test_device_id",
            CONF_NAME: "Test Light"
        },
        title="Test Light",
        entry_id="test_entry_id"
    )

async def test_light_setup(hass, mock_dlight_device, mock_config_entry):
    """Test setting up the dLight light platform."""
    mock_config_entry.add_to_hass(hass)

    # Setup the integration
    with patch("custom_components.dlight.light.AsyncDLightClient", autospec=True):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify the light entity was created
    state = hass.states.get("light.test_light")
    assert state is not None
    assert state.state == "on"
    assert state.attributes.get("brightness") == 128 # 50% of 255 is ~128
    assert state.attributes.get("color_temp_kelvin") == 4000
    assert state.attributes.get("friendly_name") == "Test Light"

async def test_light_turn_on(hass, mock_dlight_device, mock_config_entry):
    """Test turning on the dLight light."""
    mock_config_entry.add_to_hass(hass)

    with patch("custom_components.dlight.light.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Update mock to reflect expected state after commands
    mock_dlight_device.get_state.return_value = {"on": True, "brightness": 100, "color": {"temperature": 3000}}

    # Call turn_on service
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {"entity_id": "light.test_light", "brightness": 255, "color_temp_kelvin": 3000},
        blocking=True
    )

    # Verify device methods were called
    mock_dlight_device.set_brightness.assert_called_with(100) # 255 is 100%
    mock_dlight_device.set_color_temperature.assert_called_with(3000)
    
    # Verify state
    state = hass.states.get("light.test_light")
    assert state.state == "on"
    assert state.attributes.get("brightness") == 255
    assert state.attributes.get("color_temp_kelvin") == 3000

async def test_light_turn_off(hass, mock_dlight_device, mock_config_entry):
    """Test turning off the dLight light."""
    mock_config_entry.add_to_hass(hass)

    with patch("custom_components.dlight.light.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Update mock to reflect expected state after commands
    mock_dlight_device.get_state.return_value = {"on": False, "brightness": 0, "color": {"temperature": 3000}}

    # Call turn_off service
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_off",
        {"entity_id": "light.test_light"},
        blocking=True
    )

    # Verify device method was called
    mock_dlight_device.turn_off.assert_called_once()
    
    # Verify state
    state = hass.states.get("light.test_light")
    assert state.state == "off"

async def test_light_poll_update(hass, mock_dlight_device, mock_config_entry):
    """Test that the entity updates its state after a poll."""
    mock_config_entry.add_to_hass(hass)

    with patch("custom_components.dlight.light.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Get the coordinator
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]

    # Verify initial state
    state = hass.states.get("light.test_light")
    assert state.state == "on"
    assert state.attributes.get("brightness") == 128

    # Change mock return value for the next poll
    mock_dlight_device.get_state.return_value = {"on": True, "brightness": 80, "color": {"temperature": 5000}}

    # Trigger poll
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Verify updated state
    state = hass.states.get("light.test_light")
    assert state.state == "on"
    assert state.attributes.get("brightness") == 204 # 80% of 255 is 204
    assert state.attributes.get("color_temp_kelvin") == 5000

async def test_light_coordinator_error(hass, mock_dlight_device, mock_config_entry):
    """Test that the entity becomes unavailable when polling fails."""
    mock_config_entry.add_to_hass(hass)

    with patch("custom_components.dlight.light.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Get the coordinator
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]

    # Verify initial availability
    assert hass.states.get("light.test_light").state == "on"

    # Mock a connection error during poll for both state and info
    from custom_components.dlight.light import DLightConnectionError
    mock_dlight_device.get_state.side_effect = DLightConnectionError("Connection failed")
    mock_dlight_device.get_info.side_effect = DLightConnectionError("Connection failed")

    # Trigger poll
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Verify unavailability
    state = hass.states.get("light.test_light")
    assert state.state == "unavailable"

async def test_light_turn_on_no_args(hass, mock_dlight_device, mock_config_entry):
    """Test turning on the light without any extra arguments."""
    mock_config_entry.add_to_hass(hass)

    with patch("custom_components.dlight.light.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Update mock to reflect expected state after turn_off
    mock_dlight_device.get_state.return_value = {"on": False, "brightness": 0}

    # First turn it off
    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {"entity_id": "light.test_light"}, blocking=True
    )
    assert hass.states.get("light.test_light").state == "off"

    # Update mock to reflect expected state after turn_on
    mock_dlight_device.get_state.return_value = {"on": True, "brightness": 100, "color": {"temperature": 3000}}

    # Now turn it on without args
    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {"entity_id": "light.test_light"}, blocking=True
    )

    # Verify turn_on was called on device
    mock_dlight_device.turn_on.assert_called_once()
    assert hass.states.get("light.test_light").state == "on"
