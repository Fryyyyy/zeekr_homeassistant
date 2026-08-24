import asyncio
from math import nan
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from homeassistant.exceptions import HomeAssistantError
from custom_components.zeekr_ev.climate import ZeekrRefrigerationBoxClimate
from custom_components.zeekr_ev.const import DOMAIN
from custom_components.zeekr_ev.coordinator import _apply_vtm_pending
from custom_components.zeekr_ev.number import (
    ZeekrChargingLimitNumber,
    ZeekrConfigNumber,
    ZeekrRefrigerationBoxDurationNumber,
    async_setup_entry,
)


@pytest.fixture(autouse=True)
def _instant_sleep():
    """Make the post-write reconcile delay instant in tests."""
    with (
        patch("custom_components.zeekr_ev.number.asyncio.sleep", new=AsyncMock()),
        patch("custom_components.zeekr_ev.entity.asyncio.sleep", new=AsyncMock()),
    ):
        yield


class MockVehicle:
    def __init__(self, vin):
        self.vin = vin
        self.do_remote_control = MagicMock()
        self.get_vtm_status = MagicMock()
        self.data = {}


class MockCoordinator:
    def __init__(self, vehicles):
        self.vehicles = vehicles
        self.data = {v.vin: {} for v in vehicles}
        self.entry = MagicMock()
        self.entry.async_create_background_task.side_effect = (
            lambda hass, coro, name: hass.async_create_task(coro)
        )
        self.async_inc_invoke = AsyncMock()
        self.async_request_refresh = AsyncMock()
        self.seat_duration = 15
        self.last_update_success = True
        self.vtm_locks = {}
        self._vtm_pending = {}
        self._vtm_reconcile_tasks = {}
        self.request_stats = MagicMock()
        self.request_stats.async_inc_request = AsyncMock()
        self._last_secondary = {}
        self._secondary_stale_count = {}
        self._cache_vtm_status = MagicMock()
        self.listeners = []
        for vehicle in vehicles:
            vehicle.get_vtm_status.side_effect = (
                lambda vehicle=vehicle: self.data[vehicle.vin].get("vtmStatus")
            )

    def get_vehicle_by_vin(self, vin):
        for v in self.vehicles:
            if v.vin == vin:
                return v
        return None

    def async_add_listener(self, callback):
        self.listeners.append(callback)
        return MagicMock()


class DummyConfig:
    def __init__(self):
        self.config_dir = "/tmp/dummy_config_dir"

    def path(self, *args):
        return "/tmp/dummy_path"


class DummyHass:
    def __init__(self):
        self.config = DummyConfig()
        self.data = {}
        self.created_tasks = []

    async def async_add_executor_job(self, func, *args, **kwargs):
        return func(*args, **kwargs)

    def async_create_task(self, coro, *args, **kwargs):
        task = asyncio.ensure_future(coro)
        self.created_tasks.append(task)
        return task


@pytest.mark.asyncio
async def test_charging_limit_number():
    vin = "VIN1"
    vehicle = MockVehicle(vin)
    coordinator = MockCoordinator([vehicle])

    number_entity = ZeekrChargingLimitNumber(coordinator, vin)
    number_entity.hass = DummyHass()
    number_entity.async_write_ha_state = MagicMock()

    # Test setting value 80%
    await number_entity.async_set_native_value(80.0)

    coordinator.async_inc_invoke.assert_called_once()
    vehicle.do_remote_control.assert_called_with(
        "start",
        "RCS",
        {
            "serviceParameters": [
                {
                    "key": "soc",
                    "value": "800"
                },
                {
                    "key": "rcs.setting",
                    "value": "1"
                },
                {
                    "key": "altCurrent",
                    "value": "1"
                }
            ]
        }
    )

    # Check optimistic update
    assert number_entity.native_value == 80.0
    number_entity.async_write_ha_state.assert_called()

    # Drain the scheduled reconcile task to avoid a dangling pending task.
    await asyncio.gather(*number_entity.hass.created_tasks)


@pytest.mark.asyncio
async def test_charging_limit_write_reconciles_after_delay():
    """A charging-limit write updates the value immediately and schedules a refresh."""
    vin = "VIN1"
    vehicle = MockVehicle(vin)
    coordinator = MockCoordinator([vehicle])

    number_entity = ZeekrChargingLimitNumber(coordinator, vin)
    number_entity.hass = DummyHass()
    number_entity.async_write_ha_state = MagicMock()

    await number_entity.async_set_native_value(80.0)

    # Optimistic coordinator update so native_value doesn't snap back.
    assert coordinator.data[vin]["chargingLimit"]["soc"] == 800
    assert number_entity.native_value == 80.0

    # A reconcile task was scheduled; run it and confirm it refreshes.
    assert number_entity.hass.created_tasks
    await asyncio.gather(*number_entity.hass.created_tasks)
    coordinator.async_request_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_charging_limit_read_from_coordinator():
    vin = "VIN1"
    vehicle = MockVehicle(vin)
    coordinator = MockCoordinator([vehicle])

    # Inject data into coordinator
    coordinator.data[vin] = {
        "chargingLimit": {
            "soc": "900"
        }
    }

    number_entity = ZeekrChargingLimitNumber(coordinator, vin)
    number_entity.hass = DummyHass()

    # Should read 90.0
    assert number_entity.native_value == 90.0

    # Update data
    coordinator.data[vin]["chargingLimit"]["soc"] = "550"
    assert number_entity.native_value == 55.0


@pytest.mark.asyncio
async def test_charging_limit_step():
    vin = "VIN1"
    vehicle = MockVehicle(vin)
    coordinator = MockCoordinator([vehicle])

    number_entity = ZeekrChargingLimitNumber(coordinator, vin)

    assert number_entity.native_step == 5


@pytest.mark.asyncio
async def test_config_number():
    coordinator = MockCoordinator([])
    coordinator.seat_duration = 10

    number_entity = ZeekrConfigNumber(
        coordinator, "entry_id", "seat_op", "Seat Operation", "seat_duration"
    )
    number_entity.hass = DummyHass()
    number_entity.async_write_ha_state = MagicMock()

    # Check initial value
    assert number_entity.native_value == 10

    # Set value
    await number_entity.async_set_native_value(5)
    assert number_entity.native_value == 5
    assert coordinator.seat_duration == 5
    number_entity.async_write_ha_state.assert_called()

    # Test async_added_to_hass with restoration
    # Mocking async_get_last_number_data is hard because it's a mixin method
    # But we can test that it calls super().async_added_to_hass()
    # Since we can't easily mock the restore logic without full HA environment,
    # we'll skip detailed restoration test but we covered the main logic logic.


def _vtm_status(active="1", temp="3.0", duration="300"):
    return {
        "activeStatus": active,
        "currentTemperature": "2.0",
        "vtmTsActive": "false",
        "vtmModel": {
            "setting": [
                {
                    "temp": temp,
                    "duration": duration,
                }
            ]
        },
    }


@pytest.mark.asyncio
async def test_refrigeration_rechecks_authoritative_state_at_pending_expiry():
    vehicle = MockVehicle("VIN1")
    vehicle.do_remote_control.return_value = True
    coordinator = MockCoordinator([vehicle])
    coordinator.data["VIN1"] = {"vtmStatus": _vtm_status()}
    number = ZeekrRefrigerationBoxDurationNumber(coordinator, "VIN1")
    number.hass = DummyHass()
    number.async_write_ha_state = MagicMock()
    responses = [
        _vtm_status(duration="300"),
        _vtm_status(duration="600"),
    ]
    now = 0
    assert number.native_value == 5

    async def refresh():
        status = responses.pop(0)
        _apply_vtm_pending(coordinator._vtm_pending, "VIN1", status)
        coordinator.data["VIN1"]["vtmStatus"] = status

    async def advance(delay):
        nonlocal now
        now += delay

    coordinator.async_request_refresh.side_effect = refresh
    with (
        patch(
            "custom_components.zeekr_ev.coordinator.monotonic",
            side_effect=lambda: now,
        ),
        patch(
            "custom_components.zeekr_ev.entity.monotonic",
            side_effect=lambda: now,
        ),
        patch(
            "custom_components.zeekr_ev.entity.asyncio.sleep",
            side_effect=advance,
        ) as sleep,
    ):
        await number.async_set_native_value(22)
        vehicle.do_remote_control.assert_called_once_with(
            "start",
            "ZAJ",
            {
                "serviceParameters": [
                    {"key": "temp", "value": "3.0"},
                    {"key": "duration", "value": "1320"},
                    {"key": "zaj.ts", "value": "false"},
                ]
            },
        )
        assert number.native_value == 22
        await asyncio.gather(*number.hass.created_tasks)

    assert [call.args[0] for call in sleep.await_args_list] == [10, 20]
    assert coordinator.async_request_refresh.await_count == 2
    assert number.native_value == 10
    assert "VIN1" not in coordinator._vtm_pending


@pytest.mark.asyncio
async def test_refrigeration_duration_setup_requires_usable_vtm(
    hass,
    mock_config_entry,
):
    supported = MockVehicle("SUPPORTED")
    unsupported = MockVehicle("UNSUPPORTED")
    coordinator = MockCoordinator([supported, unsupported])
    coordinator.data["SUPPORTED"] = {"vtmStatus": _vtm_status()}
    hass.data[DOMAIN] = {mock_config_entry.entry_id: coordinator}
    async_add_entities = MagicMock()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    entities = async_add_entities.call_args.args[0]
    duration_entities = [
        entity
        for entity in entities
        if isinstance(entity, ZeekrRefrigerationBoxDurationNumber)
    ]
    assert [entity.vin for entity in duration_entities] == ["SUPPORTED"]


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [0, 25, nan])
async def test_refrigeration_duration_rejects_invalid_value(value):
    vehicle = MockVehicle("VIN1")
    coordinator = MockCoordinator([vehicle])
    coordinator.data["VIN1"] = {"vtmStatus": _vtm_status()}
    number = ZeekrRefrigerationBoxDurationNumber(coordinator, "VIN1")
    number.hass = DummyHass()

    with pytest.raises(HomeAssistantError):
        await number.async_set_native_value(value)

    vehicle.do_remote_control.assert_not_called()


@pytest.mark.asyncio
async def test_refrigeration_writes_do_not_clobber_each_other():
    vehicle = MockVehicle("VIN1")
    vehicle.do_remote_control.return_value = True
    coordinator = MockCoordinator([vehicle])
    coordinator.data["VIN1"] = {"vtmStatus": _vtm_status()}
    vehicle.get_vtm_status.side_effect = [_vtm_status(), _vtm_status()]

    reconcile_started = asyncio.Event()
    now = 0
    refreshed = []

    async def advance(delay):
        nonlocal now
        if not reconcile_started.is_set():
            reconcile_started.set()
            await asyncio.Future()
        now += delay

    responses = [
        _vtm_status(),
        _vtm_status(temp="4.0", duration="1320"),
    ]

    async def refresh():
        status = responses.pop(0)
        _apply_vtm_pending(coordinator._vtm_pending, "VIN1", status)
        refreshed.append((now, status["vtmModel"]["setting"][0].copy()))
        coordinator.data["VIN1"]["vtmStatus"] = status

    hass = DummyHass()
    climate = ZeekrRefrigerationBoxClimate(coordinator, "VIN1")
    duration = ZeekrRefrigerationBoxDurationNumber(coordinator, "VIN1")
    climate.hass = hass
    duration.hass = hass
    climate.async_write_ha_state = MagicMock()
    duration.async_write_ha_state = MagicMock()
    coordinator.async_request_refresh.side_effect = refresh

    with (
        patch(
            "custom_components.zeekr_ev.coordinator.monotonic",
            side_effect=lambda: now,
        ),
        patch(
            "custom_components.zeekr_ev.entity.monotonic",
            side_effect=lambda: now,
        ),
        patch(
            "custom_components.zeekr_ev.entity.asyncio.sleep",
            side_effect=advance,
        ),
    ):
        await climate.async_set_temperature(temperature=4)
        first_reconcile = hass.created_tasks[-1]
        await reconcile_started.wait()
        now = 25
        await duration.async_set_native_value(22)
        latest_reconcile = hass.created_tasks[-1]

        assert vehicle.do_remote_control.call_args_list[1].args[2][
            "serviceParameters"
        ] == [
            {"key": "temp", "value": "4.0"},
            {"key": "duration", "value": "1320"},
            {"key": "zaj.ts", "value": "false"},
        ]
        assert coordinator._vtm_reconcile_tasks["VIN1"] is latest_reconcile
        await asyncio.gather(first_reconcile, return_exceptions=True)
        assert first_reconcile.cancelled()
        await latest_reconcile

        assert refreshed == [
            (35, {"temp": "4.0", "duration": "1320"}),
            (55, {"temp": "4.0", "duration": "1320"}),
        ]
        assert "VIN1" not in coordinator._vtm_reconcile_tasks
