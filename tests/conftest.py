"""Shared fixtures for the dLight test suite."""
import copy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dlight.const import DOMAIN, CONF_DEVICE_ID


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    yield


@pytest.fixture
def mock_dlight_device():
    """Mock a dLight device (patched where it is created: the package root)."""
    with patch("custom_components.dlight.DLightDevice", autospec=True) as mock_device_class:
        mock_device = mock_device_class.return_value
        mock_device.id = "test_device_id"
        mock_device.ip = "127.0.0.1"
        mock_device._current_state = {"on": True, "brightness": 50, "color": {"temperature": 4000}}
        mock_device.get_state = AsyncMock(return_value=mock_device._current_state)
        mock_device.get_info = AsyncMock(return_value={
            "status": "SUCCESS",
            "swVersion": "1.0.0",
            "hwVersion": "1.0.0",
            "deviceModel": "Test Lamp",
            "macAddress": "AA:BB:CC:DD:EE:FF"
        })
        mock_device.turn_on = AsyncMock()
        mock_device.turn_off = AsyncMock()
        mock_device.toggle = AsyncMock()
        mock_device.ping = AsyncMock(return_value=True)
        mock_device.set_brightness = AsyncMock()
        mock_device.set_color_temperature = AsyncMock()
        mock_device.apply_scene = AsyncMock()
        mock_device.flash = AsyncMock(return_value=True)

        # Track state change callbacks
        callbacks = []
        def on_state_change(cb):
            if cb not in callbacks:
                callbacks.append(cb)
        def remove_state_listener(cb):
            if cb in callbacks:
                callbacks.remove(cb)
        mock_device.on_state_change = MagicMock(side_effect=on_state_change)
        mock_device.remove_state_listener = MagicMock(side_effect=remove_state_listener)
        mock_device._state_callbacks = callbacks

        def get_current_mock_state():
            ret = mock_device.get_state.return_value
            if isinstance(ret, dict):
                return ret
            return mock_device._current_state

        def trigger_callbacks(old_state, new_state):
            for cb in list(callbacks):
                cb(mock_device, old_state, new_state)

        async def mock_turn_on():
            state = get_current_mock_state()
            old = copy.deepcopy(state)
            state["on"] = True
            trigger_callbacks(old, copy.deepcopy(state))
        mock_device.turn_on.side_effect = mock_turn_on

        async def mock_turn_off():
            state = get_current_mock_state()
            old = copy.deepcopy(state)
            state["on"] = False
            trigger_callbacks(old, copy.deepcopy(state))
        mock_device.turn_off.side_effect = mock_turn_off

        async def mock_toggle():
            state = get_current_mock_state()
            old = copy.deepcopy(state)
            state["on"] = not state.get("on", False)
            trigger_callbacks(old, copy.deepcopy(state))
        mock_device.toggle.side_effect = mock_toggle

        async def mock_set_brightness(b):
            state = get_current_mock_state()
            old = copy.deepcopy(state)
            state["brightness"] = b
            trigger_callbacks(old, copy.deepcopy(state))
        mock_device.set_brightness.side_effect = mock_set_brightness

        async def mock_set_color_temp(k):
            state = get_current_mock_state()
            old = copy.deepcopy(state)
            if "color" not in state:
                state["color"] = {}
            state["color"]["temperature"] = k
            trigger_callbacks(old, copy.deepcopy(state))
        mock_device.set_color_temperature.side_effect = mock_set_color_temp

        async def mock_apply_scene(brightness=None, temperature=None):
            state = get_current_mock_state()
            old = copy.deepcopy(state)
            if brightness is not None:
                state["brightness"] = brightness
            if temperature is not None:
                if "color" not in state:
                    state["color"] = {}
                state["color"]["temperature"] = temperature
            trigger_callbacks(old, copy.deepcopy(state))
        mock_device.apply_scene.side_effect = mock_apply_scene

        yield mock_device


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


async def setup_integration(hass, mock_config_entry):
    """Set up the integration for a mock entry with the client patched out."""
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
