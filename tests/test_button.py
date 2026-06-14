"""Tests for the dLight identify button."""
import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from custom_components.dlight.const import DOMAIN
from .conftest import setup_integration


async def _get_button_entity_id(hass) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        "button", DOMAIN, "dlight_test_device_id_identify"
    )
    assert entity_id is not None
    return entity_id


async def test_identify_button_flashes_lamp(hass, mock_dlight_device, mock_config_entry):
    """Pressing identify runs the device's flash sequence."""
    await setup_integration(hass, mock_config_entry)
    entity_id = await _get_button_entity_id(hass)

    # Diagnostic entity, attached to the same device as the light.
    registry_entry = er.async_get(hass).async_get(entity_id)
    assert registry_entry.entity_category == er.EntityCategory.DIAGNOSTIC

    await hass.services.async_call(
        "button", "press", {"entity_id": entity_id}, blocking=True
    )
    mock_dlight_device.flash.assert_awaited_once()


async def test_identify_button_failure_raises(hass, mock_dlight_device, mock_config_entry):
    """A flash sequence that does not complete surfaces as a service error."""
    await setup_integration(hass, mock_config_entry)
    entity_id = await _get_button_entity_id(hass)

    mock_dlight_device.flash.return_value = False
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button", "press", {"entity_id": entity_id}, blocking=True
        )

    mock_dlight_device.flash.side_effect = Exception("socket torn")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button", "press", {"entity_id": entity_id}, blocking=True
        )


async def test_identify_suppresses_physical_control_event(
    hass, mock_dlight_device, mock_config_entry
):
    """A coordinator poll mid-flash must not fire a spurious physical_control event.

    Regression for #51: identify_in_progress flag on the coordinator prevents
    _handle_coordinator_update from treating mid-flash state as a physical change.
    """
    import asyncio
    from unittest.mock import AsyncMock, patch

    from custom_components.dlight.const import EVENT_PHYSICAL_CONTROL

    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    events: list = []
    hass.bus.async_listen(EVENT_PHYSICAL_CONTROL, lambda e: events.append(e))

    # Simulate a slow flash() that lets a poll sneak in mid-sequence.
    original_flash = mock_dlight_device.flash

    async def slow_flash(*args, **kwargs):
        # At the start of flash the flag should be True.
        assert coordinator.identify_in_progress is True
        # Pretend a poll arrives mid-blink with a different brightness.
        mock_dlight_device.get_state.return_value = {
            "on": True,
            "brightness": 100,
            "color": {"temperature": 6000},
        }
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        return True

    mock_dlight_device.flash = AsyncMock(side_effect=slow_flash)

    await hass.services.async_call(
        "button", "press", {"entity_id": await _get_button_entity_id(hass)}, blocking=True
    )
    await hass.async_block_till_done()

    # No physical_control event should have fired during the flash sequence.
    assert events == [], f"Spurious physical_control events fired during identify: {events}"
    # Flag must be cleared after press completes.
    assert coordinator.identify_in_progress is False

    # Simulate the post-flash restore poll returning the original state.
    # This must NOT fire a spurious event even though state differs from
    # the mid-flash value we set in slow_flash above.
    mock_dlight_device.get_state.return_value = {
        "on": True,
        "brightness": 50,
        "color": {"temperature": 4000},
    }
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert events == [], f"Spurious physical_control events fired after identify completed: {events}"

    mock_dlight_device.flash = original_flash
