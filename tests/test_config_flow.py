"""Test the dLight config flow."""
from unittest.mock import patch, AsyncMock
import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME
from custom_components.dlight.const import DOMAIN, CONF_DEVICE_ID

async def test_flow_user_manual(hass):
    """Test manual entry flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    
    # Discovery fails or returns nothing, should go to manual step
    # Wait, in my implementation it goes to discovery if devices found, else manual
    # Let's mock discover_devices to return nothing
    with patch("custom_components.dlight.config_flow.discover_devices", return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "manual"

    # Fill in the form
    with patch("custom_components.dlight.config_flow.validate_input", return_value={"title": "Test Lamp"}), \
         patch("custom_components.dlight.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: "127.0.0.1",
                CONF_DEVICE_ID: "test_id",
                CONF_NAME: "Test Lamp",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Lamp"
    assert result["data"] == {
        CONF_IP_ADDRESS: "127.0.0.1",
        CONF_DEVICE_ID: "test_id",
        CONF_NAME: "Test Lamp",
    }

async def test_flow_discovery(hass):
    """Test discovery flow."""
    mock_devices = [
        {"deviceId": "discovered_id", "ip_address": "192.168.1.50", "deviceModel": "Smart dLight"}
    ]
    
    with patch("custom_components.dlight.config_flow.discover_devices", return_value=mock_devices):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "discovery"

    # Select the discovered device
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"selected_device": "discovered_id"},
    )
    
    # It should then go to manual step (pre-filled) or create entry?
    # My implementation goes to manual step with pre-filled data
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "manual"
    
    # Finalize manual step
    with patch("custom_components.dlight.config_flow.validate_input", return_value={"title": "Smart dLight"}), \
         patch("custom_components.dlight.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: "192.168.1.50",
                CONF_DEVICE_ID: "discovered_id",
                CONF_NAME: "Smart dLight",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Smart dLight"

async def test_flow_manual_from_discovery(hass):
    """Test selecting manual entry from discovery list."""
    mock_devices = [{"deviceId": "id", "ip_address": "1.1.1.1"}]
    with patch("custom_components.dlight.config_flow.discover_devices", return_value=mock_devices):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"selected_device": "manual"},
    )
    
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "manual"
