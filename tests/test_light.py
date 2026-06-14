import asyncio

import pytest
from unittest.mock import patch
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN

from custom_components.dlight.const import DOMAIN, EVENT_PHYSICAL_CONTROL


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
    assert state.attributes.get("brightness") == 128  # 50% of 255 is ~128
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
    mock_dlight_device.get_state.return_value = {
        "on": True,
        "brightness": 100,
        "color": {"temperature": 3000},
    }

    # Call turn_on service
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {"entity_id": "light.test_light", "brightness": 255, "color_temp_kelvin": 3000},
        blocking=True,
    )

    # Both brightness and kelvin provided: apply_scene must be used atomically.
    mock_dlight_device.apply_scene.assert_called_once_with(brightness=100, temperature=3000)
    mock_dlight_device.set_brightness.assert_not_called()
    mock_dlight_device.set_color_temperature.assert_not_called()

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
    mock_dlight_device.get_state.return_value = {
        "on": False,
        "brightness": 0,
        "color": {"temperature": 3000},
    }

    # Call turn_off service
    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {"entity_id": "light.test_light"}, blocking=True
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
    mock_dlight_device.get_state.return_value = {
        "on": True,
        "brightness": 80,
        "color": {"temperature": 5000},
    }

    # Trigger poll
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Verify updated state
    state = hass.states.get("light.test_light")
    assert state.state == "on"
    assert state.attributes.get("brightness") == 204  # 80% of 255 is 204
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

    mock_dlight_device.get_state.side_effect = DLightConnectionError(
        "Connection failed"
    )

    # Trigger poll
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Verify unavailability
    state = hass.states.get("light.test_light")
    assert state.state == "unavailable"


async def test_light_setup_with_info_failure(
    hass, mock_dlight_device, mock_config_entry
):
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
    mock_dlight_device.get_state.return_value = {
        "on": True,
        "brightness": 100,
        "color": {"temperature": 3000},
    }

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


async def test_light_turn_on_with_transition(
    hass, mock_dlight_device, mock_config_entry
):
    """A transition fades brightness/temperature in steps and lands on target."""
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Initial confirmed state: on, 50%, 4000K. Fade to 100% / 3000K over 1s
    # -> 2 steps: (75%, 3500K) then (100%, 3000K).
    mock_dlight_device.get_state.return_value = {
        "on": True,
        "brightness": 100,
        "color": {"temperature": 3000},
    }
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {
            "entity_id": "light.test_light",
            "brightness": 255,
            "color_temp_kelvin": 3000,
            "transition": 1,
        },
        blocking=True,
    )
    await hass.async_block_till_done()  # waits for the tracked fade task

    assert [c.args[0] for c in mock_dlight_device.set_brightness.call_args_list] == [
        75,
        100,
    ]
    assert [
        c.args[0] for c in mock_dlight_device.set_color_temperature.call_args_list
    ] == [3500, 3000]

    state = hass.states.get("light.test_light")
    assert state.state == "on"
    assert state.attributes.get("brightness") == 255
    assert state.attributes.get("color_temp_kelvin") == 3000


async def test_light_turn_off_with_transition(
    hass, mock_dlight_device, mock_config_entry
):
    """A turn_off transition fades brightness down before the power command."""
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_dlight_device.get_state.return_value = {
        "on": False,
        "brightness": 0,
        "color": {"temperature": 4000},
    }
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_off",
        {"entity_id": "light.test_light", "transition": 1},
        blocking=True,
    )
    await hass.async_block_till_done()

    # From 50% in 2 steps: an intermediate dim, then the 1% floor, then off.
    brightness_calls = [
        c.args[0] for c in mock_dlight_device.set_brightness.call_args_list
    ]
    assert brightness_calls[-1] == 1
    assert all(0 < b < 50 for b in brightness_calls)
    mock_dlight_device.turn_off.assert_called_once()
    assert hass.states.get("light.test_light").state == "off"


async def test_light_transition_cancelled_by_new_command(
    hass, mock_dlight_device, mock_config_entry
):
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
    mock_dlight_device.get_state.return_value = {
        "on": True,
        "brightness": 20,
        "color": {"temperature": 4000},
    }
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {"entity_id": "light.test_light", "brightness": 51},
        blocking=True,
    )
    await hass.async_block_till_done()

    calls_after_cancel = len(mock_dlight_device.set_brightness.call_args_list)
    assert (
        mock_dlight_device.set_brightness.call_args_list[-1].args[0] == 20
    )  # 51/255 -> 20%
    assert hass.states.get("light.test_light").attributes.get("brightness") == 51

    # Were the fade still alive, its next step would fire within 0.5s.
    await asyncio.sleep(0.7)
    await hass.async_block_till_done()
    assert len(mock_dlight_device.set_brightness.call_args_list) == calls_after_cancel


async def test_rapid_fire_brightness_not_clobbered(
    hass, mock_dlight_device, mock_config_entry
):
    """Rapid brightness changes must not be reverted by a stale poll."""
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
            "on": True,
            "brightness": 40,
            "color": {"temperature": 4000},
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
        # The immediate poll returns the stale 40% value (lamp hasn't
        # processed B yet).
        fake_time = 1001.0
        mock_dlight_device.get_state.return_value = {
            "on": True,
            "brightness": 40,
            "color": {"temperature": 4000},
        }
        await hass.services.async_call(
            LIGHT_DOMAIN,
            "turn_on",
            {"entity_id": "light.test_light", "brightness": 204},
            blocking=True,
        )
        # The UI must still show 204 (command B's optimistic value) because
        # the stale poll was ignored.
        state = hass.states.get("light.test_light")
        assert state.attributes.get("brightness") == 204

        # Now the lamp has processed B, so the next poll returns 80%.
        # This matches optimistic state, so it is accepted immediately —
        # no need to wait for the hold window to expire.
        fake_time = 1005.0
        mock_dlight_device.get_state.return_value = {
            "on": True,
            "brightness": 80,
            "color": {"temperature": 4000},
        }
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        # The poll matches the optimistic state, so it is accepted and cleared.
        state = hass.states.get("light.test_light")
        assert state.attributes.get("brightness") == 204


async def test_single_command_poll_clears_optimistic(
    hass, mock_dlight_device, mock_config_entry
):
    """A matching poll within the hold window clears optimistic state immediately."""
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
        # The immediate poll returns 100% (lamp processed it quickly).
        mock_dlight_device.get_state.return_value = {
            "on": True,
            "brightness": 100,
            "color": {"temperature": 4000},
        }
        await hass.services.async_call(
            LIGHT_DOMAIN,
            "turn_on",
            {"entity_id": "light.test_light", "brightness": 255},
            blocking=True,
        )
        state = hass.states.get("light.test_light")
        assert state.attributes.get("brightness") == 255

        # Poll arrives with matching state — still within the hold window
        # but the state matches, so optimistic state is cleared immediately.
        fake_time = 1002.0  # only 2s later, well within 30s window
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        # Optimistic state cleared; confirmed 100% = 255.
        state = hass.states.get("light.test_light")
        assert state.attributes.get("brightness") == 255


async def test_light_toggle(hass, mock_dlight_device, mock_config_entry):
    """Test toggling the dLight light."""
    mock_config_entry.add_to_hass(hass)

    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Initial state is ON
    state = hass.states.get("light.test_light")
    assert state.state == "on"

    # Get the entity instance from EntityComponent
    entity = hass.data["light"].get_entity("light.test_light")
    assert entity is not None

    # Update mock to reflect expected state after toggle (turned off)
    mock_dlight_device.get_state.return_value = {
        "on": False,
        "brightness": 0,
        "color": {"temperature": 4000},
    }

    # Call async_toggle directly on the entity.
    # Note: We call async_toggle directly because Home Assistant's component-level
    # light.toggle service handler is hardcoded to check light.is_on and call
    # async_turn_off/async_turn_on, completely bypassing the entity's async_toggle.
    await entity.async_toggle()

    # Verify device toggle method was called
    mock_dlight_device.toggle.assert_called_once()

    # Verify state updated optimistically to off
    state = hass.states.get("light.test_light")
    assert state.state == "off"


async def test_light_toggle_error(hass, mock_dlight_device, mock_config_entry):
    """Test that toggle service raises HomeAssistantError on device error."""
    from homeassistant.exceptions import HomeAssistantError

    mock_config_entry.add_to_hass(hass)

    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Get the entity instance from EntityComponent
    entity = hass.data["light"].get_entity("light.test_light")
    assert entity is not None

    # Mock a failure during toggle
    mock_dlight_device.toggle.side_effect = Exception("Lamp command timed out")

    # Call async_toggle directly on the entity
    with pytest.raises(HomeAssistantError):
        await entity.async_toggle()

    mock_dlight_device.toggle.assert_called_once()


async def test_turn_on_with_brightness_while_off_sends_power_command(
    hass, mock_dlight_device, mock_config_entry
):
    """Regression: turn_on(brightness=X) while lamp is off must send turn_on().

    Previously, optimistic state (_optimistic_on=True) was written before the
    command list was assembled.  The guard `if not commands or not self.is_on`
    then read the already-mutated optimistic value (True), so the explicit
    turn_on() power command was never inserted when brightness was provided —
    leaving a powered-off lamp receiving only a set_brightness call.
    """
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Turn the lamp off first so is_on is False.
    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {"entity_id": "light.test_light"}, blocking=True
    )
    assert hass.states.get("light.test_light").state == "off"
    mock_dlight_device.turn_on.reset_mock()

    # Now call turn_on WITH a brightness argument while the lamp is still off.
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {"entity_id": "light.test_light", "brightness": 128},
        blocking=True,
    )

    # The explicit power-on command MUST have been sent even though brightness
    # was supplied (brightness alone doesn't power the lamp on).
    mock_dlight_device.turn_on.assert_called_once()
    # ceil(128 / 255 * 100) = 51
    mock_dlight_device.set_brightness.assert_called_with(51)


async def test_turn_on_with_kelvin_while_off_sends_power_command(
    hass, mock_dlight_device, mock_config_entry
):
    """Regression: turn_on(color_temp_kelvin=K) while off must still send turn_on().

    Companion to the brightness variant above — covers the same was_on bug for
    a colour-temperature-only turn_on call.
    """
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Turn off first.
    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {"entity_id": "light.test_light"}, blocking=True
    )
    assert hass.states.get("light.test_light").state == "off"
    mock_dlight_device.turn_on.reset_mock()

    # Call turn_on with only a colour temperature while the lamp is off.
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {"entity_id": "light.test_light", "color_temp_kelvin": 3000},
        blocking=True,
    )

    # turn_on() must be in the command batch regardless of optimistic overrides.
    mock_dlight_device.turn_on.assert_called_once()
    mock_dlight_device.set_color_temperature.assert_called_with(3000)


# ---------------------------------------------------------------------------
# apply_scene atomic command tests (issue #9)
# ---------------------------------------------------------------------------


async def test_turn_on_both_brightness_and_kelvin_uses_apply_scene(
    hass, mock_dlight_device, mock_config_entry
):
    """turn_on with both brightness and kelvin must use apply_scene (not two commands)."""
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {"entity_id": "light.test_light", "brightness": 128, "color_temp_kelvin": 4000},
        blocking=True,
    )

    mock_dlight_device.apply_scene.assert_called_once_with(brightness=51, temperature=4000)
    mock_dlight_device.set_brightness.assert_not_called()
    mock_dlight_device.set_color_temperature.assert_not_called()


async def test_turn_on_both_while_off_sends_power_then_apply_scene(
    hass, mock_dlight_device, mock_config_entry
):
    """turn_on(brightness=X, kelvin=K) while off must send turn_on() before apply_scene."""
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {"entity_id": "light.test_light"}, blocking=True
    )
    mock_dlight_device.turn_on.reset_mock()
    mock_dlight_device.apply_scene.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {"entity_id": "light.test_light", "brightness": 200, "color_temp_kelvin": 5000},
        blocking=True,
    )

    mock_dlight_device.turn_on.assert_called_once()
    mock_dlight_device.apply_scene.assert_called_once_with(brightness=79, temperature=5000)
    mock_dlight_device.set_brightness.assert_not_called()
    mock_dlight_device.set_color_temperature.assert_not_called()


async def test_turn_on_only_brightness_does_not_use_apply_scene(
    hass, mock_dlight_device, mock_config_entry
):
    """turn_on with only brightness must use set_brightness, not apply_scene."""
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {"entity_id": "light.test_light", "brightness": 100},
        blocking=True,
    )

    mock_dlight_device.apply_scene.assert_not_called()
    mock_dlight_device.set_brightness.assert_called_once()


async def test_turn_on_only_kelvin_does_not_use_apply_scene(
    hass, mock_dlight_device, mock_config_entry
):
    """turn_on with only color_temp_kelvin must use set_color_temperature, not apply_scene."""
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {"entity_id": "light.test_light", "color_temp_kelvin": 3500},
        blocking=True,
    )

    mock_dlight_device.apply_scene.assert_not_called()
    mock_dlight_device.set_color_temperature.assert_called_once_with(3500)


# ---------------------------------------------------------------------------
# Physical button press / external control event tests (issue #18)
# ---------------------------------------------------------------------------


async def test_physical_control_event_fires_on_external_off(
    hass, mock_dlight_device, mock_config_entry
):
    """A poll detecting the lamp turned off without any HA command fires the event."""
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # async_added_to_hass initializes _last_confirmed_data from coordinator.data
    # (the state fetched during async_config_entry_first_refresh), so a single
    # external-change poll is enough to detect the difference.
    coordinator = mock_config_entry.runtime_data

    events = []
    hass.bus.async_listen(EVENT_PHYSICAL_CONTROL, lambda e: events.append(e))

    # No HA command was issued, so _optimistic_on is None → outside hold window.
    mock_dlight_device.get_state.return_value = {
        "on": False,
        "brightness": 0,
        "color": {"temperature": 4000},
    }
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert len(events) == 1
    data = events[0].data
    assert data["action"] == "turned_off"
    assert data["device_id"] == "test_device_id"
    assert data["entity_id"] == "light.test_light"
    assert data["previous_state"]["on"] is True
    assert data["new_state"]["on"] is False


async def test_physical_control_event_fires_on_external_on(
    hass, mock_dlight_device, mock_config_entry
):
    """A poll detecting the lamp turned on without any HA command fires the event."""
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    # First confirm the lamp as off (no HA command, just a poll).
    mock_dlight_device.get_state.return_value = {
        "on": False,
        "brightness": 0,
        "color": {"temperature": 4000},
    }
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    events = []
    hass.bus.async_listen(EVENT_PHYSICAL_CONTROL, lambda e: events.append(e))

    # Physical button press turns it on.
    mock_dlight_device.get_state.return_value = {
        "on": True,
        "brightness": 100,
        "color": {"temperature": 4000},
    }
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["action"] == "turned_on"


async def test_physical_control_event_fires_on_brightness_change(
    hass, mock_dlight_device, mock_config_entry
):
    """A poll showing brightness change (lamp stays on) fires action='changed'."""
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    events = []
    hass.bus.async_listen(EVENT_PHYSICAL_CONTROL, lambda e: events.append(e))

    # Lamp stays on but someone physically changed brightness to 80%.
    mock_dlight_device.get_state.return_value = {
        "on": True,
        "brightness": 80,
        "color": {"temperature": 4000},
    }
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert len(events) == 1
    data = events[0].data
    assert data["action"] == "changed"
    assert data["new_state"]["brightness"] == 80
    assert data["previous_state"]["brightness"] == 50


async def test_physical_control_not_fired_on_first_poll(
    hass, mock_dlight_device, mock_config_entry
):
    """No event fires during integration setup even though a baseline is established.

    async_added_to_hass snapshots coordinator.data (from async_config_entry_first_refresh)
    as the initial _last_confirmed_data. No coordinator refresh fires during setup, so
    no state comparison happens and no event is dispatched.
    """
    events = []

    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        # Register listener before setup so it captures any event from first_refresh.
        hass.bus.async_listen(EVENT_PHYSICAL_CONTROL, lambda e: events.append(e))
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert events == []


async def test_physical_control_not_fired_within_hold_window(
    hass, mock_dlight_device, mock_config_entry
):
    """No event fires for a state change caused by an HA service call."""
    mock_config_entry.add_to_hass(hass)

    fake_time = 1000.0

    def monotonic():
        return fake_time

    with patch("custom_components.dlight.light.time") as mock_time:
        mock_time.monotonic = monotonic

        with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        coordinator = mock_config_entry.runtime_data

        events = []
        hass.bus.async_listen(EVENT_PHYSICAL_CONTROL, lambda e: events.append(e))

        # HA sends a turn_off; _last_command_time is set to fake_time=1000.
        mock_dlight_device.get_state.return_value = {
            "on": False,
            "brightness": 0,
            "color": {"temperature": 4000},
        }
        await hass.services.async_call(
            LIGHT_DOMAIN, "turn_off", {"entity_id": "light.test_light"}, blocking=True
        )

        # Poll at the same fake_time → within hold window (0s elapsed < 30s).
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        assert events == []


async def test_physical_control_not_fired_when_state_unchanged(
    hass, mock_dlight_device, mock_config_entry
):
    """No event fires when successive outside-window polls return identical state."""
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    events = []
    hass.bus.async_listen(EVENT_PHYSICAL_CONTROL, lambda e: events.append(e))

    # Two polls — same state as the initial confirmed data.
    for _ in range(2):
        mock_dlight_device.get_state.return_value = {
            "on": True,
            "brightness": 50,
            "color": {"temperature": 4000},
        }
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert events == []


async def test_physical_control_not_fired_during_transition(
    hass, mock_dlight_device, mock_config_entry
):
    """No event fires while an emulated fade transition is active."""
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    entity = hass.data["light"].get_entity("light.test_light")

    events = []
    hass.bus.async_listen(EVENT_PHYSICAL_CONTROL, lambda e: events.append(e))

    # Start a 20-second fade — the task runs in the background and is sleeping
    # between steps. asyncio.sleep uses real wall time, so async_block_till_done
    # would wait up to 20 real seconds if not cancelled first.
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {"entity_id": "light.test_light", "brightness": 255, "transition": 20},
        blocking=True,
    )
    assert entity._transition_task is not None and not entity._transition_task.done()

    # Poll while the fade is active — simulating an external state change.
    # coordinator.async_refresh() awaits completion synchronously; by the time it
    # returns, _handle_coordinator_update has already been called and returned early
    # (transition guard), so no event has been scheduled.
    mock_dlight_device.get_state.return_value = {
        "on": False,
        "brightness": 0,
        "color": {"temperature": 4000},
    }
    await coordinator.async_refresh()

    # Assert immediately — before calling async_block_till_done, which would
    # wait for the 20-second fade to complete and might trigger post-fade logic.
    assert events == []

    # Cleanup: cancel the fade so the test doesn't block for 20 real seconds.
    await entity._async_cancel_transition()
