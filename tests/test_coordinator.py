"""Test Zeekr coordinator."""
import pytest
from unittest.mock import AsyncMock
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.zeekr_ev.coordinator import ZeekrCoordinator


async def test_coordinator_update_success(hass: HomeAssistant, mock_zeekr_api):
    """Test successful coordinator update."""
    coordinator = ZeekrCoordinator(hass, mock_zeekr_api, timedelta(seconds=30))
    
    await coordinator.async_config_entry_first_refresh()
    
    assert coordinator.data is not None
    assert "vehicles" in coordinator.data
    assert len(coordinator.data["vehicles"]) > 0


async def test_coordinator_update_interval(hass: HomeAssistant, mock_zeekr_api):
    """Test coordinator respects update interval."""
    update_interval = timedelta(seconds=30)
    coordinator = ZeekrCoordinator(hass, mock_zeekr_api, update_interval)
    
    assert coordinator.update_interval == update_interval


async def test_coordinator_handles_api_error(hass: HomeAssistant, mock_zeekr_api):
    """Test coordinator handles API errors gracefully."""
    mock_zeekr_api.get_vehicles.side_effect = Exception("API Error")
    
    coordinator = ZeekrCoordinator(hass, mock_zeekr_api, timedelta(seconds=30))
    
    with pytest.raises(Exception):
        await coordinator.async_config_entry_first_refresh()
