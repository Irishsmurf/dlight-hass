"""Tests for DLightCoordinator's rediscovery fallback."""
from unittest.mock import patch

from dlightclient import DLightConnectionError

from homeassistant.const import CONF_IP_ADDRESS

from custom_components.dlight.const import REDISCOVERY_FAILURE_THRESHOLD
from .conftest import setup_integration


def make_stream(*devices):
    """Return an async-generator mock that yields *devices* then stops."""

    async def _gen(*args, **kwargs):
        for d in devices:
            yield d

    return _gen


async def test_rediscovery_heals_ip_after_consecutive_failures(
    hass, mock_dlight_device, mock_config_entry
):
    """N failed polls in a row trigger a UDP sweep that updates the entry IP."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    mock_dlight_device.get_state.side_effect = DLightConnectionError("gone")
    mock_dlight_device.ping.return_value = False
    stream = make_stream({"deviceId": "test_device_id", "ip_address": "10.0.0.99"})
    with patch("custom_components.dlight.coordinator.discover_devices_stream", stream):
        for _ in range(REDISCOVERY_FAILURE_THRESHOLD - 1):
            await coordinator.async_refresh()

        await coordinator.async_refresh()  # Nth consecutive failure
        await hass.async_block_till_done()

    assert mock_config_entry.data[CONF_IP_ADDRESS] == "10.0.0.99"


async def test_rediscovery_same_ip_leaves_entry_alone(
    hass, mock_dlight_device, mock_config_entry
):
    """Finding the lamp on its known IP (TCP-only outage) changes nothing."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    mock_dlight_device.get_state.side_effect = DLightConnectionError("gone")
    mock_dlight_device.ping.return_value = False
    stream = make_stream({"deviceId": "test_device_id", "ip_address": "127.0.0.1"})
    with patch("custom_components.dlight.coordinator.discover_devices_stream", stream):
        for _ in range(REDISCOVERY_FAILURE_THRESHOLD):
            await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert mock_config_entry.data[CONF_IP_ADDRESS] == "127.0.0.1"


async def test_successful_poll_resets_failure_counter(
    hass, mock_dlight_device, mock_config_entry
):
    """Intermittent failures never accumulate to a rediscovery sweep."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    stream_called = False

    async def tracking_stream(*args, **kwargs):
        nonlocal stream_called
        stream_called = True
        if False:
            yield

    with patch(
        "custom_components.dlight.coordinator.discover_devices_stream", tracking_stream
    ):
        for _ in range(REDISCOVERY_FAILURE_THRESHOLD + 2):
            # fail once...
            mock_dlight_device.get_state.side_effect = DLightConnectionError("blip")
            await coordinator.async_refresh()
            # ...then recover: the counter must reset
            mock_dlight_device.get_state.side_effect = None
            await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert not stream_called


async def test_rediscovery_skipped_if_ping_succeeds(
    hass, mock_dlight_device, mock_config_entry
):
    """If the device fails state polling but answers ping, we skip the UDP sweep."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    mock_dlight_device.get_state.side_effect = DLightConnectionError("gone")
    mock_dlight_device.ping.return_value = True

    stream_called = False

    async def tracking_stream(*args, **kwargs):
        nonlocal stream_called
        stream_called = True
        if False:
            yield

    with patch(
        "custom_components.dlight.coordinator.discover_devices_stream", tracking_stream
    ):
        for _ in range(REDISCOVERY_FAILURE_THRESHOLD):
            await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert not stream_called
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


async def test_coordinator_setup_ping_exception(
    hass, mock_dlight_device, mock_config_entry
):
    """If ping raises an exception during setup, we treat it as offline, return early and skip get_info."""
    mock_dlight_device.ping.side_effect = Exception("ping crash")

    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.dlight.AsyncDLightClient", autospec=True):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_dlight_device.ping.assert_called_with(timeout=2.0)
    mock_dlight_device.get_info.assert_not_called()


async def test_rediscovery_ping_exception_triggers_sweep(
    hass, mock_dlight_device, mock_config_entry
):
    """If ping raises an exception during rediscovery, we proceed with the UDP sweep."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    mock_dlight_device.get_state.side_effect = DLightConnectionError("gone")
    mock_dlight_device.ping.side_effect = Exception("ping crash")

    stream_called = False

    async def tracking_stream(*args, **kwargs):
        nonlocal stream_called
        stream_called = True
        if False:
            yield

    with patch(
        "custom_components.dlight.coordinator.discover_devices_stream", tracking_stream
    ):
        for _ in range(REDISCOVERY_FAILURE_THRESHOLD):
            await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert stream_called
    mock_dlight_device.ping.assert_called_with(timeout=2.0)


async def test_rediscovery_breaks_early_on_first_match(
    hass, mock_dlight_device, mock_config_entry
):
    """The stream loop breaks as soon as the target device is found (early exit)."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    mock_dlight_device.get_state.side_effect = DLightConnectionError("gone")
    mock_dlight_device.ping.return_value = False

    yielded = []

    async def tracking_stream(*args, **kwargs):
        for device in [
            {"deviceId": "other_device", "ip_address": "10.0.0.50"},
            {"deviceId": "test_device_id", "ip_address": "10.0.0.99"},
            {"deviceId": "another_device", "ip_address": "10.0.0.51"},
        ]:
            yielded.append(device["deviceId"])
            yield device

    with patch(
        "custom_components.dlight.coordinator.discover_devices_stream", tracking_stream
    ):
        for _ in range(REDISCOVERY_FAILURE_THRESHOLD):
            await coordinator.async_refresh()
        await hass.async_block_till_done()

    # Should have yielded the first two devices but broken before the third
    assert "test_device_id" in yielded
    assert "another_device" not in yielded
    assert mock_config_entry.data[CONF_IP_ADDRESS] == "10.0.0.99"
