from custom_components.zeekr_ev.coordinator import ZeekrCoordinator


class FakeVehicle:
    def __init__(self, vin, status, charging_status=None):
        self.vin = vin
        self._status = status
        self._charging_status = charging_status

    def get_status(self):
        return self._status

    def get_charging_status(self):
        return self._charging_status


class FakeClient:
    def __init__(self, vehicles):
        self._vehicles = vehicles

    def get_vehicle_list(self):
        return self._vehicles


async def test_get_vehicle_by_vin(hass, mock_config_entry, monkeypatch):
    # Mock the daily reset setup to avoid Home Assistant event system issues in tests
    monkeypatch.setattr(ZeekrCoordinator, "_setup_daily_reset", lambda self: None)

    client = FakeClient([])
    coordinator = ZeekrCoordinator(hass=hass, client=client, entry=mock_config_entry)
    v1 = FakeVehicle("VIN1", {})
    v2 = FakeVehicle("VIN2", {})
    coordinator.vehicles = [v1, v2]

    assert coordinator.get_vehicle_by_vin("VIN1") is v1
    assert coordinator.get_vehicle_by_vin("UNKNOWN") is None


async def test_async_update_data_fetches_list_and_status(hass, mock_config_entry, monkeypatch):
    # Mock the daily reset setup to avoid Home Assistant event system issues in tests
    monkeypatch.setattr(ZeekrCoordinator, "_setup_daily_reset", lambda self: None)

    v1 = FakeVehicle("VIN1", {"k": "v"})
    client = FakeClient([v1])

    # Provide a coordinator with our fake hass and client
    coordinator = ZeekrCoordinator(hass=hass, client=client, entry=mock_config_entry)

    data = await coordinator._async_update_data()
    assert "VIN1" in data
    assert data["VIN1"] == {"k": "v"}


async def test_async_update_data_fetches_charging_status_when_charging(hass, mock_config_entry, monkeypatch):
    """Test that charging status is fetched when vehicle is charging."""
    # Mock the daily reset setup to avoid Home Assistant event system issues in tests
    monkeypatch.setattr(ZeekrCoordinator, "_setup_daily_reset", lambda self: None)

    status = {
        "additionalVehicleStatus": {
            "electricVehicleStatus": {"isCharging": True}
        }
    }
    charging_status = {
        "chargerState": "2",
        "chargeVoltage": "222.0",
        "chargeCurrent": "9.4",
        "chargeSpeed": "8",
        "chargePower": "2.1",
    }
    v1 = FakeVehicle("VIN1", status, charging_status)
    client = FakeClient([v1])

    coordinator = ZeekrCoordinator(hass=hass, client=client, entry=mock_config_entry)

    data = await coordinator._async_update_data()
    assert "VIN1" in data
    assert "chargingStatus" in data["VIN1"]
    assert data["VIN1"]["chargingStatus"]["chargeVoltage"] == "222.0"


async def test_async_update_data_skips_charging_status_when_not_charging(hass, mock_config_entry, monkeypatch):
    """Test that charging status is not fetched when vehicle is not charging."""
    # Mock the daily reset setup to avoid Home Assistant event system issues in tests
    monkeypatch.setattr(ZeekrCoordinator, "_setup_daily_reset", lambda self: None)

    status = {
        "additionalVehicleStatus": {
            "electricVehicleStatus": {"isCharging": False}
        }
    }
    v1 = FakeVehicle("VIN1", status, None)
    client = FakeClient([v1])

    coordinator = ZeekrCoordinator(hass=hass, client=client, entry=mock_config_entry)

    data = await coordinator._async_update_data()
    assert "VIN1" in data
    # chargingStatus should not be set if vehicle is not charging
    assert data["VIN1"].get("chargingStatus") is None or data["VIN1"]["chargingStatus"] == {}
