"""Tests for DLightCoordinator's rediscovery fallback."""
from unittest.mock import AsyncMock, patch

from dlightclient import DLightConnectionError

from homeassistant.const import CONF_IP_ADDRESS

from custom_components.dlight.const import REDISCOVERY_FAILURE_THRESHOLD
from .conftest import setup_integration


async def test_rediscovery_heals_ip_after_consecutive_failures(
    hass, mock_dlight_device, mock_config_entry
):
    """N failed polls in a row trigger a UDP sweep that updates the entry IP."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    mock_dlight_device.get_state.side_effect = DLightConnectionError("gone")
    mock_dlight_device.ping.return_value = False
    sweep = AsyncMock(
        return_value=[{"deviceId": "test_device_id", "ip_address": "10.0.0.99"}]
    )
    with patch("custom_components.dlight.coordinator.discover_devices", sweep):
        for _ in range(REDISCOVERY_FAILURE_THRESHOLD - 1):
            await coordinator.async_refresh()
        sweep.assert_not_called()  # still below the threshold

        await coordinator.async_refresh()  # Nth consecutive failure
        await hass.async_block_till_done()

    sweep.assert_awaited_once()
    assert mock_config_entry.data[CONF_IP_ADDRESS] == "10.0.0.99"


async def test_rediscovery_same_ip_leaves_entry_alone(
    hass, mock_dlight_device, mock_config_entry
):
    """Finding the lamp on its known IP (TCP-only outage) changes nothing."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    mock_dlight_device.get_state.side_effect = DLightConnectionError("gone")
    mock_dlight_device.ping.return_value = False
    sweep = AsyncMock(
        return_value=[{"deviceId": "test_device_id", "ip_address": "127.0.0.1"}]
    )
    with patch("custom_components.dlight.coordinator.discover_devices", sweep):
        for _ in range(REDISCOVERY_FAILURE_THRESHOLD):
            await coordinator.async_refresh()
        await hass.async_block_till_done()

    sweep.assert_awaited_once()
    assert mock_config_entry.data[CONF_IP_ADDRESS] == "127.0.0.1"


async def test_successful_poll_resets_failure_counter(
    hass, mock_dlight_device, mock_config_entry
):
    """Intermittent failures never accumulate to a rediscovery sweep."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    sweep = AsyncMock(return_value=[])
    with patch("custom_components.dlight.coordinator.discover_devices", sweep):
        for _ in range(REDISCOVERY_FAILURE_THRESHOLD + 2):
            # fail once...
            mock_dlight_device.get_state.side_effect = DLightConnectionError("blip")
            await coordinator.async_refresh()
            # ...then recover: the counter must reset
            mock_dlight_device.get_state.side_effect = None
            await coordinator.async_refresh()
        await hass.async_block_till_done()

    sweep.assert_not_called()


async def test_rediscovery_skipped_if_ping_succeeds(
    hass, mock_dlight_device, mock_config_entry
):
    """If the device fails state polling but answers ping, we skip the UDP sweep."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    mock_dlight_device.get_state.side_effect = DLightConnectionError("gone")
    mock_dlight_device.ping.return_value = True
    sweep = AsyncMock(return_value=[])

    with patch("custom_components.dlight.coordinator.discover_devices", sweep):
        for _ in range(REDISCOVERY_FAILURE_THRESHOLD):
            await coordinator.async_refresh()
        await hass.async_block_till_done()

    sweep.assert_not_called()
    mock_dlight_device.ping.assert_called_with(timeout=2.0)


async def test_coordinator_setup_ping_failure(
    hass, mock_dlight_device, mock_config_entry
):
    """If ping fails during coordinator setup, we return early and skip get_info."""
    mock_dlight_device.ping.return_value = False

    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_dlight_device.ping.assert_called_with(timeout=2.0)
    mock_dlight_device.get_info.assert_not_called()

