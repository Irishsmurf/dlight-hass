import asyncio

import pytest
from unittest.mock import patch
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN

from custom_components.dlight.const import DOMAIN

async def test_light_setup(hass, mock_dlight_device, mock_config_entry):
    """Test setting up the dLight light platform."""
    mock_config_entry.add_to_hass(hass)

    # Setup the integration
    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify the light entity was created
    state = hass.states.get("light.test_light")
    assert state is not None
    assert state.state == "on"
    assert state.attributes.get("brightness") == 128 # 50% of 255 is ~128
    assert state.attributes.get("color_temp_kelvin") == 4000
    assert state.attributes.get("friendly_name") == "Test Light"

    # Verify MAC address in device info
    from homeassistant.helpers import device_registry as dr
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, "test_device_id")})
    assert device is not None
    assert (dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff") in device.connections

async def test_light_turn_on(hass, mock_dlight_device, mock_config_entry):
    """Test turning on the dLight light."""
    mock_config_entry.add_to_hass(hass)

    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
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

    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
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

    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Get the coordinator from the entry's typed runtime data
    coordinator = mock_config_entry.runtime_data

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

    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Get the coordinator from the entry's typed runtime data
    coordinator = mock_config_entry.runtime_data

    # Verify initial availability
    assert hass.states.get("light.test_light").state == "on"

    # Mock a connection error during the state poll (info is only fetched
    # once at setup, so it plays no part in ongoing availability)
    from dlightclient import DLightConnectionError
    mock_dlight_device.get_state.side_effect = DLightConnectionError("Connection failed")

    # Trigger poll
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Verify unavailability
    state = hass.states.get("light.test_light")
    assert state.state == "unavailable"

async def test_light_setup_with_info_failure(hass, mock_dlight_device, mock_config_entry):
    """A failed device info query must not block entity creation.

    Info is cosmetic (registry card); the entity should still appear with a
    generic model as long as the state poll works.
    """
    from dlightclient import DLightConnectionError
    mock_dlight_device.get_info.side_effect = DLightConnectionError("info offline")
    mock_config_entry.add_to_hass(hass)

    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("light.test_light")
    assert state is not None
    assert state.state == "on"
    assert state.attributes.get("brightness") == 128

async def test_light_turn_on_no_args(hass, mock_dlight_device, mock_config_entry):
    """Test turning on the light without any extra arguments."""
    mock_config_entry.add_to_hass(hass)

    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
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

async def test_light_service_error(hass, mock_dlight_device, mock_config_entry):
    """Test that a HomeAssistantError is raised when a service call fails."""
    from homeassistant.exceptions import HomeAssistantError
    mock_config_entry.add_to_hass(hass)

    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Mock a failure during turn_on
    mock_dlight_device.turn_on.side_effect = Exception("Lamp exploded")

    # Communication failures are HomeAssistantError (device unreachable), not
    # ServiceValidationError (which would imply the user's input was invalid).
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LIGHT_DOMAIN, "turn_on", {"entity_id": "light.test_light"}, blocking=True
        )



async def test_light_supports_transition(hass, mock_dlight_device, mock_config_entry):
    """The entity must advertise transition support (emulated fades)."""
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("light.test_light")
    from homeassistant.components.light import LightEntityFeature
    assert state.attributes["supported_features"] & LightEntityFeature.TRANSITION

async def test_light_turn_on_with_transition(hass, mock_dlight_device, mock_config_entry):
    """A transition fades brightness/temperature in steps and lands on target."""
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Initial confirmed state: on, 50%, 4000K. Fade to 100% / 3000K over 1s
    # -> 2 steps: (75%, 3500K) then (100%, 3000K).
    mock_dlight_device.get_state.return_value = {"on": True, "brightness": 100, "color": {"temperature": 3000}}
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {"entity_id": "light.test_light", "brightness": 255, "color_temp_kelvin": 3000, "transition": 1},
        blocking=True,
    )
    await hass.async_block_till_done()  # waits for the tracked fade task

    assert [c.args[0] for c in mock_dlight_device.set_brightness.call_args_list] == [75, 100]
    assert [c.args[0] for c in mock_dlight_device.set_color_temperature.call_args_list] == [3500, 3000]

    state = hass.states.get("light.test_light")
    assert state.state == "on"
    assert state.attributes.get("brightness") == 255
    assert state.attributes.get("color_temp_kelvin") == 3000

async def test_light_turn_off_with_transition(hass, mock_dlight_device, mock_config_entry):
    """A turn_off transition fades brightness down before the power command."""
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_dlight_device.get_state.return_value = {"on": False, "brightness": 0, "color": {"temperature": 4000}}
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_off",
        {"entity_id": "light.test_light", "transition": 1},
        blocking=True,
    )
    await hass.async_block_till_done()

    # From 50% in 2 steps: an intermediate dim, then the 1% floor, then off.
    brightness_calls = [c.args[0] for c in mock_dlight_device.set_brightness.call_args_list]
    assert brightness_calls[-1] == 1
    assert all(0 < b < 50 for b in brightness_calls)
    mock_dlight_device.turn_off.assert_called_once()
    assert hass.states.get("light.test_light").state == "off"

async def test_light_transition_cancelled_by_new_command(hass, mock_dlight_device, mock_config_entry):
    """A new command interrupts a running fade; no further steps are sent."""
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Long fade: 20s -> 40 steps every 0.5s. Only the first step (eager) runs
    # before the instant command below cancels the task.
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {"entity_id": "light.test_light", "brightness": 255, "transition": 20},
        blocking=True,
    )
    mock_dlight_device.get_state.return_value = {"on": True, "brightness": 20, "color": {"temperature": 4000}}
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {"entity_id": "light.test_light", "brightness": 51},
        blocking=True,
    )
    await hass.async_block_till_done()

    calls_after_cancel = len(mock_dlight_device.set_brightness.call_args_list)
    assert mock_dlight_device.set_brightness.call_args_list[-1].args[0] == 20  # 51/255 -> 20%
    assert hass.states.get("light.test_light").attributes.get("brightness") == 51

    # Were the fade still alive, its next step would fire within 0.5s.
    await asyncio.sleep(0.7)
    await hass.async_block_till_done()
    assert len(mock_dlight_device.set_brightness.call_args_list) == calls_after_cancel

async def test_rapid_fire_brightness_not_clobbered(hass, mock_dlight_device, mock_config_entry):
    """Rapid brightness changes must not be reverted by a stale poll.

    Scenario: the user drags a slider quickly — command A, then command B.
    A stale poll (still showing A's result) arrives before the lamp has
    processed B.  Without the rapid-fire guard, the UI would snap back to A.
    """
    mock_config_entry.add_to_hass(hass)

    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    fake_time = 1000.0

    def monotonic():
        return fake_time

    with patch("custom_components.dlight.light.time") as mock_time:
        mock_time.monotonic = monotonic

        # Command A: set brightness to ~40%
        mock_dlight_device.get_state.return_value = {
            "on": True, "brightness": 40, "color": {"temperature": 4000}
        }
        await hass.services.async_call(
            LIGHT_DOMAIN,
            "turn_on",
            {"entity_id": "light.test_light", "brightness": 102},
            blocking=True,
        )
        state = hass.states.get("light.test_light")
        assert state.attributes.get("brightness") == 102

        # Command B: set brightness to ~80% 1 second later.
        fake_time = 1001.0
        mock_dlight_device.get_state.return_value = {
            "on": True, "brightness": 80, "color": {"temperature": 4000}
        }
        await hass.services.async_call(
            LIGHT_DOMAIN,
            "turn_on",
            {"entity_id": "light.test_light", "brightness": 204},
            blocking=True,
        )
        state = hass.states.get("light.test_light")
        assert state.attributes.get("brightness") == 204

        # Simulate a stale poll arriving with command A's result (40%),
        # still within the hold window after command B.
        fake_time = 1005.0  # 4s after B, well within the 30s POLL_INTERVAL
        mock_dlight_device.get_state.return_value = {
            "on": True, "brightness": 40, "color": {"temperature": 4000}
        }
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        # The UI must still show 204 (command B's optimistic value).
        state = hass.states.get("light.test_light")
        assert state.attributes.get("brightness") == 204

        # Advance past the hold window.  The next poll is trusted.
        fake_time = 1032.0  # 31s after command B
        mock_dlight_device.get_state.return_value = {
            "on": True, "brightness": 80, "color": {"temperature": 4000}
        }
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        # Optimistic state cleared; confirmed 80% = ceil(80/100*255) = 204.
        state = hass.states.get("light.test_light")
        assert state.attributes.get("brightness") == 204


async def test_single_command_poll_clears_optimistic(hass, mock_dlight_device, mock_config_entry):
    """A poll arriving after the hold window should clear optimistic state normally."""
    mock_config_entry.add_to_hass(hass)

    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    fake_time = 1000.0

    def monotonic():
        return fake_time

    with patch("custom_components.dlight.light.time") as mock_time:
        mock_time.monotonic = monotonic

        # Single command: set brightness to 100%.
        mock_dlight_device.get_state.return_value = {
            "on": True, "brightness": 100, "color": {"temperature": 4000}
        }
        await hass.services.async_call(
            LIGHT_DOMAIN,
            "turn_on",
            {"entity_id": "light.test_light", "brightness": 255},
            blocking=True,
        )
        state = hass.states.get("light.test_light")
        assert state.attributes.get("brightness") == 255

        # Advance past the hold window, then poll.
        fake_time = 1031.0
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        # Optimistic state cleared; confirmed 100% = 255.
        state = hass.states.get("light.test_light")
        assert state.attributes.get("brightness") == 255
