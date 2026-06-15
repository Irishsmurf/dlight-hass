"""Tests for __init__.py: entry lifecycle, client cleanup, and listener registration."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from dlightclient import DLightConnectionError
from homeassistant.config_entries import ConfigEntryNotReady
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dlight.const import CONF_DEVICE_ID, DOMAIN
from custom_components.dlight import SERVICE_FLASH
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


# ---------------------------------------------------------------------------
# dlight.flash service tests (issue #78)
# ---------------------------------------------------------------------------


async def test_flash_service_registered_on_setup(hass, mock_dlight_device, mock_config_entry):
    """dlight.flash service is registered after a successful entry setup."""
    await setup_integration(hass, mock_config_entry)
    assert hass.services.has_service(DOMAIN, SERVICE_FLASH)


async def test_flash_service_calls_device_flash(hass, mock_dlight_device, mock_config_entry):
    """Calling dlight.flash finds the coordinator and calls device.flash()."""
    mock_dlight_device.flash.return_value = True
    await setup_integration(hass, mock_config_entry)

    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(identifiers={(DOMAIN, "test_device_id")})
    assert device is not None

    await hass.services.async_call(
        DOMAIN,
        SERVICE_FLASH,
        {"device_id": device.id},
        blocking=True,
    )

    mock_dlight_device.flash.assert_called_once()


async def test_flash_service_unknown_device_raises(hass, mock_dlight_device, mock_config_entry):
    """Calling dlight.flash with an unknown device_id raises ServiceValidationError."""
    from homeassistant.exceptions import ServiceValidationError

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_FLASH,
            {"device_id": "nonexistent-device-id"},
            blocking=True,
        )


async def test_flash_service_raises_on_device_flash_failure(hass, mock_dlight_device, mock_config_entry):
    """dlight.flash raises HomeAssistantError when flash() returns False."""
    from homeassistant.exceptions import HomeAssistantError

    mock_dlight_device.flash.return_value = False
    await setup_integration(hass, mock_config_entry)

    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(identifiers={(DOMAIN, "test_device_id")})
    assert device is not None

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_FLASH,
            {"device_id": device.id},
            blocking=True,
        )


async def test_flash_service_raises_on_empty_device_id(hass, mock_dlight_device, mock_config_entry):
    """dlight.flash raises ServiceValidationError when called with an empty device_id."""
    from homeassistant.exceptions import ServiceValidationError

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_FLASH,
            {"device_id": ""},
            blocking=True,
        )


async def test_flash_service_raises_on_device_flash_exception(hass, mock_dlight_device, mock_config_entry):
    """dlight.flash raises HomeAssistantError when flash() throws an exception."""
    from homeassistant.exceptions import HomeAssistantError

    mock_dlight_device.flash.side_effect = Exception("device exploded")
    await setup_integration(hass, mock_config_entry)

    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(identifiers={(DOMAIN, "test_device_id")})
    assert device is not None

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_FLASH,
            {"device_id": device.id},
            blocking=True,
        )


async def test_flash_service_raises_when_no_coordinator_for_device(hass, mock_dlight_device, mock_config_entry):
    """dlight.flash raises ServiceValidationError when the device has no loaded coordinator."""
    from homeassistant.exceptions import ServiceValidationError
    from homeassistant.helpers import device_registry as dr_module

    await setup_integration(hass, mock_config_entry)

    # Add a second device entry linked only to a "ghost" entry with no coordinator.
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"ip_address": "10.0.0.1", "device_id": "ghost_id"},
        title="Ghost Lamp",
        entry_id="ghost_entry_id",
    )
    other_entry.add_to_hass(hass)
    dev_reg = dr_module.async_get(hass)
    ghost_device = dev_reg.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={(DOMAIN, "ghost_id")},
        name="Ghost Lamp",
    )

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_FLASH,
            {"device_id": ghost_device.id},
            blocking=True,
        )


async def test_flash_service_removed_on_last_entry_unload(hass, mock_dlight_device, mock_config_entry):
    """dlight.flash service is removed when the last entry is unloaded."""
    await setup_integration(hass, mock_config_entry)
    assert hass.services.has_service(DOMAIN, SERVICE_FLASH)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service(DOMAIN, SERVICE_FLASH)
