"""Shared fixtures for the dLight test suite."""
from unittest.mock import AsyncMock, patch

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
        mock_device.get_state = AsyncMock(return_value={"on": True, "brightness": 50, "color": {"temperature": 4000}})
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
        mock_device.set_brightness = AsyncMock()
        mock_device.set_color_temperature = AsyncMock()
        mock_device.flash = AsyncMock(return_value=True)
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
