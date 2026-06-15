"""Tests for __init__.py: entry lifecycle, client cleanup, and listener registration."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from dlightclient import DLightConnectionError
from homeassistant.config_entries import ConfigEntryNotReady
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.exceptions import ConfigEntryError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dlight.const import CONF_DEVICE_ID, DOMAIN
from .conftest import setup_integration


async def test_setup_entry_populates_runtime_data(hass, mock_dlight_device, mock_config_entry):
    """Successful setup stores a coordinator in entry.runtime_data."""
    await setup_integration(hass, mock_config_entry)
    from custom_components.dlight.coordinator import DLightCoordinator
    assert isinstance(mock_config_entry.runtime_data, DLightCoordinator)


async def test_setup_entry_registers_state_listener(hass, mock_dlight_device, mock_config_entry):
    """setup_entry registers the coordinator's push-state listener on the device."""
    await setup_integration(hass, mock_config_entry)
    mock_dlight_device.on_state_change.assert_called_once()


async def test_unload_entry_closes_client(hass, mock_dlight_device, mock_config_entry):
    """async_unload_entry triggers client.close() via the registered unload hook."""
    with patch("custom_components.dlight.AsyncDLightClient", autospec=True) as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.close = AsyncMock()
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_client.close.assert_called_once()


async def test_unload_entry_removes_state_listener(hass, mock_dlight_device, mock_config_entry):
    """async_unload_entry removes the push-state listener from the device."""
    await setup_integration(hass, mock_config_entry)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_dlight_device.remove_state_listener.assert_called_once()


async def test_setup_entry_raises_config_entry_not_ready_on_failed_refresh(
    hass, mock_dlight_device, mock_config_entry
):
    """If the first coordinator refresh fails, ConfigEntryNotReady is raised."""
    mock_dlight_device.get_state.side_effect = DLightConnectionError("unreachable")

    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert result is False
    assert mock_config_entry.state.value == "setup_retry"


async def test_setup_entry_closes_client_on_failed_refresh(hass, mock_dlight_device, mock_config_entry):
    """If the first refresh fails, client.close() is still called (no connection leak)."""
    mock_dlight_device.get_state.side_effect = DLightConnectionError("unreachable")

    with patch("custom_components.dlight.AsyncDLightClient", autospec=True) as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.close = AsyncMock()
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # client.close is registered as an unload hook — on failed setup the entry
    # is torn down, which fires the hook.
    mock_client.close.assert_called_once()


async def test_setup_entry_raises_config_entry_error_on_missing_ip(hass, mock_dlight_device):
    """ConfigEntryError is raised immediately when IP address is absent from entry data."""
    bad_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE_ID: "test_device_id"},  # no CONF_IP_ADDRESS
        title="Bad Entry",
        entry_id="bad_entry_id",
    )
    bad_entry.add_to_hass(hass)
    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        result = await hass.config_entries.async_setup(bad_entry.entry_id)

    assert result is False
    assert bad_entry.state.value == "setup_error"


async def test_setup_entry_raises_config_entry_error_on_missing_device_id(hass, mock_dlight_device):
    """ConfigEntryError is raised immediately when device ID is absent from entry data."""
    bad_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "127.0.0.1"},  # no CONF_DEVICE_ID
        title="Bad Entry",
        entry_id="bad_entry_id2",
    )
    bad_entry.add_to_hass(hass)
    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        result = await hass.config_entries.async_setup(bad_entry.entry_id)

    assert result is False
    assert bad_entry.state.value == "setup_error"


async def test_options_change_triggers_entry_reload(hass, mock_dlight_device, mock_config_entry):
    """Saving options (e.g. poll_interval) triggers a reload of the config entry."""
    await setup_integration(hass, mock_config_entry)

    with patch.object(hass.config_entries, "async_reload", return_value=True) as mock_reload:
        # async_update_entry is sync in HA; it fires all registered update_listeners.
        hass.config_entries.async_update_entry(
            mock_config_entry, options={"poll_interval": 15}
        )
        await hass.async_block_till_done()

    mock_reload.assert_called_once_with(mock_config_entry.entry_id)
