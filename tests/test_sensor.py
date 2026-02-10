"""Test Zeekr sensors."""
from homeassistant.core import HomeAssistant
from homeassistant.const import (
    PERCENTAGE,
    UnitOfLength,
    UnitOfTemperature,
)

from custom_components.zeekr_ev.const import DOMAIN
from .const import MOCK_VEHICLE_DATA


async def test_battery_sensor(hass: HomeAssistant, mock_zeekr_integration):
    """Test battery level sensor."""
    state = hass.states.get(f"sensor.{MOCK_VEHICLE_DATA['name'].lower().replace(' ', '_')}_battery")
    
    assert state is not None
    assert state.state == str(MOCK_VEHICLE_DATA["batteryLevel"])
    assert state.attributes.get("unit_of_measurement") == PERCENTAGE


async def test_range_sensor(hass: HomeAssistant, mock_zeekr_integration):
    """Test range sensor."""
    state = hass.states.get(f"sensor.{MOCK_VEHICLE_DATA['name'].lower().replace(' ', '_')}_range")
    
    assert state is not None
    assert state.state == str(MOCK_VEHICLE_DATA["range"])


async def test_odometer_sensor(hass: HomeAssistant, mock_zeekr_integration):
    """Test odometer sensor."""
    state = hass.states.get(f"sensor.{MOCK_VEHICLE_DATA['name'].lower().replace(' ', '_')}_odometer")
    
    assert state is not None
    assert state.state == str(MOCK_VEHICLE_DATA["odometer"])


async def test_temperature_sensor(hass: HomeAssistant, mock_zeekr_integration):
    """Test interior temperature sensor."""
    state = hass.states.get(
        f"sensor.{MOCK_VEHICLE_DATA['name'].lower().replace(' ', '_')}_interior_temperature"
    )
    
    assert state is not None
    assert float(state.state) == MOCK_VEHICLE_DATA["interiorTemperature"]
    assert state.attributes.get("unit_of_measurement") == UnitOfTemperature.CELSIUS
