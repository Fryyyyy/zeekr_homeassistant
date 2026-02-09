"""Test Zeekr EV integration initialization."""
import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.zeekr_ev.const import DOMAIN


async def test_setup_entry(hass: HomeAssistant, mock_zeekr_integration):
    """Test successful setup of config entry."""
    assert mock_zeekr_integration.state == ConfigEntryState.LOADED
    assert DOMAIN in hass.data


async def test_unload_entry(hass: HomeAssistant, mock_zeekr_integration):
    """Test unloading config entry."""
    entry = mock_zeekr_integration
    
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    
    assert entry.state == ConfigEntryState.NOT_LOADED
    assert DOMAIN not in hass.data


async def test_reload_entry(hass: HomeAssistant, mock_zeekr_integration):
    """Test reloading config entry."""
    entry = mock_zeekr_integration
    
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    
    assert entry.state == ConfigEntryState.LOADED


async def test_setup_entry_authentication_error(
    hass: HomeAssistant, mock_config_entry, mock_zeekr_api
):
    """Test setup fails with authentication error."""
    mock_config_entry.add_to_hass(hass)
    mock_zeekr_api.login.side_effect = Exception("Authentication failed")
    
    with pytest.raises(Exception):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
