"""Test dLight diagnostics output."""
from unittest.mock import patch, AsyncMock

from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dlight.const import DOMAIN, CONF_DEVICE_ID
from custom_components.dlight.diagnostics import async_get_config_entry_diagnostics


async def test_diagnostics_redacts_identifiers(hass):
    """Diagnostics include state/info but redact network identifiers."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_DEVICE_ID: "test_device_id",
            CONF_NAME: "Test Light",
        },
        title="Test Light",
        unique_id="dlight_test_device_id",
    )
    entry.add_to_hass(hass)

    with patch("custom_components.dlight.DLightDevice", autospec=True) as mock_device_class, \
         patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        mock_device = mock_device_class.return_value
        mock_device.id = "test_device_id"
        mock_device.ip = "127.0.0.1"
        mock_device.get_state = AsyncMock(
            return_value={"on": True, "brightness": 50, "color": {"temperature": 4000}}
        )
        mock_device.get_info = AsyncMock(
            return_value={
                "status": "SUCCESS",
                "swVersion": "1.0.0",
                "hwVersion": "1.0.0",
                "deviceModel": "Test Lamp",
                "macAddress": "AA:BB:CC:DD:EE:FF",
            }
        )

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    # Network/device identifiers are scrubbed; harmless fields survive
    assert diagnostics["entry"]["data"][CONF_IP_ADDRESS] == "**REDACTED**"
    assert diagnostics["entry"]["data"][CONF_DEVICE_ID] == "**REDACTED**"
    assert diagnostics["entry"]["data"][CONF_NAME] == "Test Light"

    # The useful debugging payload is present
    assert diagnostics["state"] == {
        "on": True,
        "brightness": 50,
        "color": {"temperature": 4000},
    }
    assert diagnostics["device_info"]["deviceModel"] == "Test Lamp"
    assert diagnostics["device_info"]["swVersion"] == "1.0.0"
    assert diagnostics["device_info"]["hwVersion"] == "1.0.0"
    assert diagnostics["device_info"]["macAddress"] == "**REDACTED**"
    assert diagnostics["last_update_success"] is True
    assert diagnostics["update_interval"] == "0:00:30"

    # Coordinator health fields are present and sane after a successful setup
    health = diagnostics["coordinator_health"]
    assert health["consecutive_failures"] == 0
    assert health["last_success"] is not None  # set by the initial poll
    assert health["rediscovery_in_flight"] is False


async def test_diagnostics_coordinator_health_on_failure(hass, mock_dlight_device, mock_config_entry):
    """coordinator_health reflects consecutive failures; last_success retains the pre-failure timestamp."""
    from dlightclient import DLightConnectionError
    from .conftest import setup_integration

    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    # Simulate two consecutive poll failures
    mock_dlight_device.get_state.side_effect = DLightConnectionError("offline")
    await coordinator.async_refresh()
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    health = diagnostics["coordinator_health"]
    assert health["consecutive_failures"] == 2
    assert health["last_success"] is not None  # timestamp from initial successful poll
    assert health["rediscovery_in_flight"] is False
