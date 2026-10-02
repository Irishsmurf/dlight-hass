"""Tests for DLightCoordinator's rediscovery fallback."""
from datetime import timedelta
from unittest.mock import patch

from dlightclient import DLightConnectionError

from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dlight.const import (
    CONF_DEVICE_ID,
    CONF_POLL_INTERVAL,
    DOMAIN,
    INFO_RETRY_INTERVAL,
    REDISCOVERY_FAILURE_THRESHOLD,
)
from .conftest import setup_integration


async def test_coordinator_uses_options_poll_interval(hass, mock_dlight_device):
    """Coordinator update_interval reflects entry options rather than the hardcoded default."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "127.0.0.1", CONF_DEVICE_ID: "test_device_id", CONF_NAME: "Test Light"},
        options={CONF_POLL_INTERVAL: 15},
        title="Test Light",
        entry_id="test_entry_poll",
    )
    await setup_integration(hass, entry)
    assert entry.runtime_data.update_interval == timedelta(seconds=15)


async def test_coordinator_defaults_to_30s_without_options(hass, mock_dlight_device, mock_config_entry):
    """Coordinator falls back to 30-second default when no poll_interval option is set."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.runtime_data.update_interval == timedelta(seconds=30)


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


# ---------------------------------------------------------------------------
# Late device-info fetch (issue #93)
# ---------------------------------------------------------------------------

INFO_OK = {
    "status": "SUCCESS",
    "swVersion": "1.0.0",
    "hwVersion": "1.0.0",
    "deviceModel": "Test Lamp",
    "macAddress": "AA:BB:CC:DD:EE:FF",
}


def _device_entry(hass):
    return dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "test_device_id")})


def _firmware_state(hass):
    entity_id = er.async_get(hass).async_get_entity_id("update", DOMAIN, "dlight_test_device_id_firmware")
    return hass.states.get(entity_id)


async def test_device_info_retried_after_failed_setup(hass, mock_dlight_device, mock_config_entry, freezer):
    """get_info failing at setup is retried after a later poll and fills the device card."""
    mock_dlight_device.get_info.side_effect = [DLightConnectionError("slow wifi"), INFO_OK]
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    device = _device_entry(hass)
    assert coordinator.info == {}
    assert device.model == "dLight" and device.sw_version is None
    assert _firmware_state(hass).state == "unavailable"

    freezer.tick(timedelta(seconds=INFO_RETRY_INTERVAL + 1))
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    device = _device_entry(hass)
    assert device.model == "Test Lamp"
    assert device.sw_version == "1.0.0"
    assert device.hw_version == "1.0.0"
    assert (dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff") in device.connections
    assert _firmware_state(hass).state == "off"


async def test_device_info_retry_is_throttled(hass, mock_dlight_device, mock_config_entry, freezer):
    """A lamp that keeps failing get_info is asked at most once per INFO_RETRY_INTERVAL."""
    mock_dlight_device.get_info.side_effect = DLightConnectionError("nope")
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    assert mock_dlight_device.get_info.await_count == 1

    for _ in range(5):  # polls inside the interval: no retry
        freezer.tick(timedelta(seconds=30))
        await coordinator.async_refresh()
    assert mock_dlight_device.get_info.await_count == 1

    freezer.tick(timedelta(seconds=INFO_RETRY_INTERVAL))
    await coordinator.async_refresh()
    await coordinator.async_refresh()
    assert mock_dlight_device.get_info.await_count == 2
    assert coordinator.last_update_success  # a failed info retry never fails the poll


async def test_device_info_not_refetched_when_setup_succeeded(hass, mock_dlight_device, mock_config_entry, freezer):
    """With info cached at setup, polls never query get_info again."""
    await setup_integration(hass, mock_config_entry)
    freezer.tick(timedelta(seconds=INFO_RETRY_INTERVAL * 2))
    await mock_config_entry.runtime_data.async_refresh()
    assert mock_dlight_device.get_info.await_count == 1
    assert _device_entry(hass).manufacturer == "dLight"
