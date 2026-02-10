"""Common fixtures for the Zeekr EV tests."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from custom_components.zeekr_ev.const import DOMAIN
from .const import MOCK_CONFIG, MOCK_VEHICLE_DATA

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Automatically enable custom integrations for all tests."""
    yield


@pytest.fixture
def mock_zeekr_api():
    """Mock Zeekr API client."""
    with patch(
        "custom_components.zeekr_ev.ZeekrAPI", autospec=True
    ) as mock_api:
        api = mock_api.return_value
        api.login = AsyncMock(return_value=True)
        api.get_vehicles = AsyncMock(return_value=[
            MagicMock(
                vin=MOCK_VEHICLE_DATA["vin"],
                name=MOCK_VEHICLE_DATA["name"],
                battery_level=MOCK_VEHICLE_DATA["batteryLevel"],
                range=MOCK_VEHICLE_DATA["range"],
                odometer=MOCK_VEHICLE_DATA["odometer"],
                location=MOCK_VEHICLE_DATA["location"],
                is_charging=MOCK_VEHICLE_DATA["isCharging"],
                is_plugged_in=MOCK_VEHICLE_DATA["isPluggedIn"],
                interior_temperature=MOCK_VEHICLE_DATA["interiorTemperature"],
                tire_pressures=MOCK_VEHICLE_DATA["tirePressures"],
                doors=MOCK_VEHICLE_DATA["doors"],
            )
        ])
        yield api


@pytest.fixture
def mock_config_entry():
    """Mock a config entry."""
    from homeassistant.config_entries import ConfigEntry
    
    return ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Test Zeekr",
        data=MOCK_CONFIG,
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
    )


@pytest.fixture
async def mock_zeekr_integration(hass: HomeAssistant, mock_config_entry, mock_zeekr_api):
    """Set up the Zeekr integration with mocked data."""
    mock_config_entry.add_to_hass(hass)
    
    with patch(
        "custom_components.zeekr_ev.ZeekrAPI",
        return_value=mock_zeekr_api,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        
    return mock_config_entry
