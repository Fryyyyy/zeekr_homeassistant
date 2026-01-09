from custom_components.zeekr_ev.lock import ZeekrLock


class DummyCoordinator:
    def __init__(self, data):
        self.data = data


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
