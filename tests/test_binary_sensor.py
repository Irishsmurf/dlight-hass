"""Tests for the dLight connectivity binary sensor."""
from dlightclient import DLightConnectionError

from homeassistant.helpers import entity_registry as er

from custom_components.dlight.const import DOMAIN, POLL_INTERVAL, REDISCOVERY_FAILURE_THRESHOLD
from .conftest import setup_integration


async def test_connectivity_sensor_tracks_poll_health(
    hass, mock_dlight_device, mock_config_entry
):
    """The sensor reports on/off with poll health and never goes unavailable."""
    await setup_integration(hass, mock_config_entry)

    entity_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor", DOMAIN, "dlight_test_device_id_connectivity"
    )
    assert entity_id is not None
    registry_entry = er.async_get(hass).async_get(entity_id)
    assert registry_entry.entity_category == er.EntityCategory.DIAGNOSTIC

    assert hass.states.get(entity_id).state == "on"

    # Lamp drops off the network: the light goes unavailable, but the
    # connectivity sensor must stay available and flip to "off" — that
    # failure is precisely the data it reports.
    mock_dlight_device.get_state.side_effect = DLightConnectionError("gone")
    coordinator = mock_config_entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("light.test_light").state == "unavailable"
    assert hass.states.get(entity_id).state == "off"

    # Lamp comes back: sensor returns to "on".
    mock_dlight_device.get_state.side_effect = None
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "on"


async def test_connectivity_sensor_health_attributes_healthy(
    hass, mock_dlight_device, mock_config_entry
):
    """Health attributes reflect zero failures and a timestamp after a good poll."""
    await setup_integration(hass, mock_config_entry)
    entity_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor", DOMAIN, "dlight_test_device_id_connectivity"
    )
    state = hass.states.get(entity_id)
    attrs = state.attributes

    assert attrs["consecutive_failures"] == 0
    assert attrs["last_successful_poll"] is not None  # set by setup poll
    assert attrs["rediscovery_triggered"] is False
    assert attrs["poll_interval_seconds"] == POLL_INTERVAL


async def test_connectivity_sensor_health_attributes_degraded(
    hass, mock_dlight_device, mock_config_entry
):
    """consecutive_failures increments on poll errors; rediscovery_triggered flips at threshold."""
    from unittest.mock import patch as _patch

    await setup_integration(hass, mock_config_entry)
    entity_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor", DOMAIN, "dlight_test_device_id_connectivity"
    )
    coordinator = mock_config_entry.runtime_data
    last_good_poll = coordinator.last_successful_poll

    mock_dlight_device.get_state.side_effect = DLightConnectionError("gone")
    # Suppress rediscovery so the test doesn't trigger an entry reload.
    with _patch.object(coordinator, "_async_attempt_rediscovery", return_value=None):
        for _ in range(REDISCOVERY_FAILURE_THRESHOLD):
            await coordinator.async_refresh()
            await hass.async_block_till_done()

    # Check coordinator state directly (entity state cache may only update on
    # last_update_success transitions, not every failure increment).
    assert coordinator.consecutive_failures == REDISCOVERY_FAILURE_THRESHOLD
    assert coordinator.last_successful_poll is not None
    assert coordinator.last_successful_poll == last_good_poll
    assert coordinator.consecutive_failures >= REDISCOVERY_FAILURE_THRESHOLD  # rediscovery_triggered

    # Recovery: failures reset, timestamp refreshes, rediscovery_triggered clears.
    mock_dlight_device.get_state.side_effect = None
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    attrs = hass.states.get(entity_id).attributes
    assert attrs["consecutive_failures"] == 0
    assert attrs["rediscovery_triggered"] is False
    assert attrs["last_successful_poll"] != last_good_poll


async def test_connectivity_sensor_last_successful_poll_none_before_first_success(
    hass, mock_dlight_device, mock_config_entry
):
    """last_successful_poll is None until the first poll succeeds."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    # Manually reset to simulate a coordinator that has never had a good poll.
    coordinator._last_successful_poll = None
    coordinator._consecutive_failures = 1

    # Trigger a refresh that fails to keep the state consistent.
    mock_dlight_device.get_state.side_effect = DLightConnectionError("gone")
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    entity_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor", DOMAIN, "dlight_test_device_id_connectivity"
    )
    attrs = hass.states.get(entity_id).attributes
    assert attrs["last_successful_poll"] is None
