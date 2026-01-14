import pytest
from unittest.mock import MagicMock
from custom_components.zeekr_ev.lock import ZeekrLock


class MockVehicle:
    def __init__(self, vin):
        self.vin = vin

    def do_remote_control(self, command, service_id, setting):
        return True


class MockCoordinator:
    def __init__(self, data):
        self.data = data
        self.vehicles = {}

    def get_vehicle_by_vin(self, vin):
        return self.vehicles.get(vin)

    def inc_invoke(self):
        pass

    async def async_request_refresh(self):
        pass


class DummyHass:
    def __init__(self):
        self.loop = MagicMock()
        self.loop.create_task = MagicMock()

    async def async_add_executor_job(self, func, *args, **kwargs):
        return func(*args, **kwargs)

    def async_create_task(self, task):
        pass


class DummyCoordinator:
    def __init__(self, data):
        self.data = data


# Keeping existing tests...
def test_is_locked_none_when_missing():
    data = {"VIN1": {"additionalVehicleStatus": {"drivingSafetyStatus": {}}}}
    coordinator = DummyCoordinator(data)
    lk = ZeekrLock(coordinator, "VIN1", "doorLockStatusDriver", "Driver door lock", "drivingSafetyStatus")
    assert lk.is_locked is None


def test_is_locked_openstatus_logic():
    # For fields ending with OpenStatus: "1" -> open -> locked False
    data_open = {"VIN1": {"additionalVehicleStatus": {"drivingSafetyStatus": {"trunkOpenStatus": "1"}}}}
    coordinator = DummyCoordinator(data_open)
    lk = ZeekrLock(coordinator, "VIN1", "trunkOpenStatus", "Trunk open", "drivingSafetyStatus")
    assert lk.is_locked is False

    data_closed = {"VIN1": {"additionalVehicleStatus": {"drivingSafetyStatus": {"trunkOpenStatus": "0"}}}}
    coordinator = DummyCoordinator(data_closed)
    lk = ZeekrLock(coordinator, "VIN1", "trunkOpenStatus", "Trunk open", "drivingSafetyStatus")
    assert lk.is_locked is True


def test_is_locked_regular_field():
    data_locked = {"VIN1": {"additionalVehicleStatus": {"drivingSafetyStatus": {"doorLockStatusDriver": "1"}}}}
    coordinator = DummyCoordinator(data_locked)
    lk = ZeekrLock(coordinator, "VIN1", "doorLockStatusDriver", "Driver door lock", "drivingSafetyStatus")
    assert lk.is_locked is True

    data_unlocked = {"VIN1": {"additionalVehicleStatus": {"drivingSafetyStatus": {"doorLockStatusDriver": "0"}}}}
    coordinator = DummyCoordinator(data_unlocked)
    lk = ZeekrLock(coordinator, "VIN1", "doorLockStatusDriver", "Driver door lock", "drivingSafetyStatus")
    assert lk.is_locked is False


def test_is_locked_charge_lid_logic():
    # "1" = Open (Unlocked), "2" = Closed (Locked)
    data_open = {"VIN1": {"additionalVehicleStatus": {"electricVehicleStatus": {"chargeLidDcAcStatus": "1"}}}}
    coordinator = DummyCoordinator(data_open)
    lk = ZeekrLock(coordinator, "VIN1", "chargeLidDcAcStatus", "Charge Lid", "electricVehicleStatus")
    assert lk.is_locked is False

    data_closed = {"VIN1": {"additionalVehicleStatus": {"electricVehicleStatus": {"chargeLidDcAcStatus": "2"}}}}
    coordinator = DummyCoordinator(data_closed)
    lk = ZeekrLock(coordinator, "VIN1", "chargeLidDcAcStatus", "Charge Lid", "electricVehicleStatus")
    assert lk.is_locked is True


# New async tests
@pytest.mark.asyncio
async def test_lock_optimistic_update_central_locking():
    vin = "VIN1"
    initial_data = {
        vin: {
            "additionalVehicleStatus": {
                "drivingSafetyStatus": {
                    "centralLockingStatus": "0"  # Unlocked
                }
            }
        }
    }

    coordinator = MockCoordinator(initial_data)
    coordinator.vehicles[vin] = MockVehicle(vin)

    lock = ZeekrLock(coordinator, vin, "centralLockingStatus", "Central locking", "drivingSafetyStatus")
    lock.hass = DummyHass()
    lock.async_write_ha_state = MagicMock()

    # Test Lock
    await lock.async_lock()

    status = coordinator.data[vin]["additionalVehicleStatus"]["drivingSafetyStatus"]
    assert status["centralLockingStatus"] == "1"
    lock.async_write_ha_state.assert_called()

    # Test Unlock
    await lock.async_unlock()

    status = coordinator.data[vin]["additionalVehicleStatus"]["drivingSafetyStatus"]
    assert status["centralLockingStatus"] == "0"
    lock.async_write_ha_state.assert_called()


@pytest.mark.asyncio
async def test_lock_optimistic_update_charge_lid():
    vin = "VIN1"
    initial_data = {
        vin: {
            "additionalVehicleStatus": {
                "electricVehicleStatus": {
                    "chargeLidDcAcStatus": "1"  # Open/Unlocked
                }
            }
        }
    }

    coordinator = MockCoordinator(initial_data)
    coordinator.vehicles[vin] = MockVehicle(vin)

    lock = ZeekrLock(coordinator, vin, "chargeLidDcAcStatus", "Charge Lid", "electricVehicleStatus")
    lock.hass = DummyHass()
    lock.async_write_ha_state = MagicMock()

    # Test Lock (Close)
    await lock.async_lock()

    status = coordinator.data[vin]["additionalVehicleStatus"]["electricVehicleStatus"]
    assert status["chargeLidDcAcStatus"] == "2"  # Closed/Locked
    lock.async_write_ha_state.assert_called()

    # Test Unlock (Open)
    await lock.async_unlock()

    status = coordinator.data[vin]["additionalVehicleStatus"]["electricVehicleStatus"]
    assert status["chargeLidDcAcStatus"] == "1"  # Open/Unlocked
    lock.async_write_ha_state.assert_called()
