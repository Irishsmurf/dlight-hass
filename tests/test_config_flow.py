"""Test the dLight config flow."""
from datetime import timedelta
from unittest.mock import patch, AsyncMock
import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dlight.const import DOMAIN, CONF_DEVICE_ID

async def test_flow_user_manual(hass):
    """Test manual entry flow via the discovery_none step."""
    # With no devices discovered, the flow shows the discovery_none interstitial
    with patch("custom_components.dlight.config_flow.discover_devices", return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.FlowResultType.MENU
        assert result["step_id"] == "discovery_none"

    # User chooses manual entry
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "manual"},
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

    # Selecting a device pre-fills the manual step, which validates the
    # lamp and creates the entry directly
    with patch("custom_components.dlight.config_flow.validate_input", return_value={"title": "Smart dLight"}), \
         patch("custom_components.dlight.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"selected_device": "discovered_id"},
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Smart dLight"
    assert result["data"] == {
        CONF_IP_ADDRESS: "192.168.1.50",
        CONF_DEVICE_ID: "discovered_id",
        CONF_NAME: "Smart dLight",
    }

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

async def test_discovery_none_shows_interstitial(hass):
    """When discovery returns no results, the flow shows the discovery_none step."""
    with patch("custom_components.dlight.config_flow.discover_devices", return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == data_entry_flow.FlowResultType.MENU
    assert result["step_id"] == "discovery_none"


async def test_discovery_none_retry_reruns_discovery(hass):
    """Choosing 'retry' from discovery_none reruns discovery and shows lamps if found."""
    mock_devices = [
        {"deviceId": "lamp_id", "ip_address": "192.168.1.55", "deviceModel": "dLight"}
    ]
    with patch("custom_components.dlight.config_flow.discover_devices", return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["step_id"] == "discovery_none"

    # Retry: this time discovery finds a lamp
    with patch("custom_components.dlight.config_flow.discover_devices", return_value=mock_devices):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "retry"},
        )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "discovery"


async def test_discovery_none_retry_still_empty_shows_interstitial_again(hass):
    """Retrying when discovery still finds nothing shows discovery_none again."""
    with patch("custom_components.dlight.config_flow.discover_devices", return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["step_id"] == "discovery_none"

    with patch("custom_components.dlight.config_flow.discover_devices", return_value=[]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "retry"},
        )
    assert result["type"] == data_entry_flow.FlowResultType.MENU
    assert result["step_id"] == "discovery_none"


async def test_discovery_heals_changed_ip(hass):
    """A known lamp rediscovered on a new IP gets its entry updated silently."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "192.168.1.10", CONF_DEVICE_ID: "known_id"},
        title="Known Lamp",
        unique_id="dlight_known_id",
    )
    entry.add_to_hass(hass)

    # Same lamp, new address (e.g. after a DHCP lease change)
    mock_devices = [
        {"deviceId": "known_id", "ip_address": "192.168.1.99", "deviceModel": "dLight"}
    ]
    with patch("custom_components.dlight.config_flow.discover_devices", return_value=mock_devices), \
         patch("custom_components.dlight.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    # The healed lamp is not offered again; with nothing new the flow shows discovery_none
    assert result["type"] == data_entry_flow.FlowResultType.MENU
    assert result["step_id"] == "discovery_none"
    # ...but its stored IP has been refreshed
    assert entry.data[CONF_IP_ADDRESS] == "192.168.1.99"

async def test_retry_does_not_heal_known_lamp_ip(hass):
    """Regression for #50: async_step_retry must NOT update entries for known lamps.

    When a user clicks "Try again" from discovery_none, the intent is to scan
    for *new* lamps. If a known lamp appears on a new IP during that scan it
    must be silently ignored — self-healing is reserved for the initial user
    step so that an unexpected coordinator reload cannot fire mid-use.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "192.168.1.10", CONF_DEVICE_ID: "known_id"},
        title="Known Lamp",
        unique_id="dlight_known_id",
    )
    entry.add_to_hass(hass)

    # First init: no devices found → discovery_none
    with patch("custom_components.dlight.config_flow.discover_devices", return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["step_id"] == "discovery_none"

    # Retry: known lamp appears on a new IP
    mock_devices = [
        {"deviceId": "known_id", "ip_address": "192.168.1.99", "deviceModel": "dLight"}
    ]
    with patch("custom_components.dlight.config_flow.discover_devices", return_value=mock_devices), \
         patch.object(hass.config_entries, "async_update_entry") as mock_update, \
         patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "retry"},
        )
        await hass.async_block_till_done()

    # The retry must not have healed the entry
    mock_update.assert_not_called()
    mock_reload.assert_not_called()
    # Stored IP unchanged
    assert entry.data[CONF_IP_ADDRESS] == "192.168.1.10"
    # Known lamp was filtered out → still no new devices → discovery_none again
    assert result["type"] == data_entry_flow.FlowResultType.MENU
    assert result["step_id"] == "discovery_none"


async def test_manual_readd_updates_ip(hass):
    """Manually re-adding a configured lamp aborts but heals its stored IP."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "192.168.1.10", CONF_DEVICE_ID: "test_id"},
        title="Test Lamp",
        unique_id="dlight_test_id",
    )
    entry.add_to_hass(hass)

    with patch("custom_components.dlight.config_flow.discover_devices", return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["step_id"] == "discovery_none"

    # Advance past the discovery_none interstitial
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "manual"},
    )
    assert result["step_id"] == "manual"

    with patch("custom_components.dlight.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: "192.168.1.99",
                CONF_DEVICE_ID: "test_id",
                CONF_NAME: "Test Lamp",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_IP_ADDRESS] == "192.168.1.99"

async def test_flow_reconfigure(hass):
    """The reconfigure flow updates the stored IP for the same lamp."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "192.168.1.10",
            CONF_DEVICE_ID: "test_id",
            CONF_NAME: "Test Lamp",
        },
        title="Test Lamp",
        unique_id="dlight_test_id",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch("custom_components.dlight.config_flow.validate_input", return_value={"title": "Test Lamp"}), \
         patch("custom_components.dlight.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: "192.168.1.99",
                CONF_DEVICE_ID: "test_id",
                CONF_NAME: "Test Lamp",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_IP_ADDRESS] == "192.168.1.99"

async def test_flow_reconfigure_rejects_different_lamp(hass):
    """Reconfigure with a different device id aborts: it must stay the same lamp."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "192.168.1.10", CONF_DEVICE_ID: "test_id"},
        title="Test Lamp",
        unique_id="dlight_test_id",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IP_ADDRESS: "192.168.1.10",
            CONF_DEVICE_ID: "other_id",
            CONF_NAME: "Test Lamp",
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"

async def test_no_options_flow(hass):
    """Regression: the options flow was removed (ADR-0010), and a leftover
    async_get_options_flow hook would make HA render a broken Configure button."""
    from custom_components.dlight.config_flow import DLightConfigFlow

    entry = MockConfigEntry(domain=DOMAIN)
    assert not DLightConfigFlow.async_supports_options_flow(entry)

# --- DHCP discovery -------------------------------------------------------

from dataclasses import dataclass

@dataclass
class _DhcpInfo:
    """Stand-in for DhcpServiceInfo (whose module needs deps absent here)."""
    ip: str
    hostname: str
    macaddress: str

async def _add_entry_with_registered_mac(hass, ip="192.168.1.10"):
    """Create a configured lamp whose MAC is in the device registry."""
    from homeassistant.helpers import device_registry as dr

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: ip, CONF_DEVICE_ID: "test_id"},
        title="Test Lamp",
        unique_id="dlight_test_id",
    )
    entry.add_to_hass(hass)
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "test_id")},
        connections={(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff")},
    )
    return entry

async def test_dhcp_discovery_heals_changed_ip(hass):
    """A DHCP lease for a known MAC on a new IP updates the entry."""
    entry = await _add_entry_with_registered_mac(hass, ip="192.168.1.10")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=_DhcpInfo(ip="192.168.1.99", hostname="dlight", macaddress="aabbccddeeff"),
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_IP_ADDRESS] == "192.168.1.99"

async def test_dhcp_discovery_same_ip_aborts_quietly(hass):
    """A lease renewal on the same IP changes nothing."""
    entry = await _add_entry_with_registered_mac(hass, ip="192.168.1.10")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=_DhcpInfo(ip="192.168.1.10", hostname="dlight", macaddress="aabbccddeeff"),
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_IP_ADDRESS] == "192.168.1.10"

async def test_dhcp_discovery_unknown_mac_aborts(hass):
    """DHCP traffic from a MAC we don't know is ignored."""
    await _add_entry_with_registered_mac(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=_DhcpInfo(ip="192.168.1.50", hostname="other", macaddress="112233445566"),
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "unknown_device"
