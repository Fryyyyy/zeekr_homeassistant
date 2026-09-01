"""Shared entity implementations for Zeekr EV API Integration."""

from __future__ import annotations

import asyncio
from time import monotonic

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    _apply_vtm_pending,
    _merge_vtm_off_status,
    get_vtm_setting,
    VTM_SETTLE_SECONDS,
    ZeekrCoordinator,
)

import logging
_LOGGER = logging.getLogger(__name__)


def setup_refrigeration_box_discovery(
    coordinator,
    entry,
    async_add_entities,
    entities,
    entity_class,
) -> None:
    """Add fitted refrigeration-box entities now and after later discovery."""
    known_vins: set[str] = set()

    def discover():
        discovered = [
            entity_class(coordinator, vin)
            for vin, vehicle_data in coordinator.data.items()
            if vin not in known_vins
            and get_vtm_setting(vehicle_data.get("vtmStatus")) is not None
        ]
        known_vins.update(entity.vin for entity in discovered)
        return discovered

    entities.extend(discover())

    def add_discovered() -> None:
        if discovered := discover():
            async_add_entities(discovered)

    entry.async_on_unload(coordinator.async_add_listener(add_discovered))


class ZeekrEntity(CoordinatorEntity[ZeekrCoordinator]):
    """Base entity for Zeekr."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ZeekrCoordinator, vin: str) -> None:
        """Initialize."""
        super().__init__(coordinator)

        # Set device info
        self.vin = vin
        vehicle = coordinator.get_vehicle_by_vin(vin)
        if vehicle:
            plate_no = getattr(vehicle, "data", {}).get("plateNo")
            display_os_version = getattr(vehicle, "data", {}).get("displayOSVersion")

            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, vin)},
                name=vehicle.vin,
                manufacturer="Zeekr",
                model=f"{plate_no} (OS Version {display_os_version})" if display_os_version else plate_no or "Zeekr EV",
            )


class ZeekrRefrigerationBoxEntity(ZeekrEntity):
    """Shared refrigeration-box state and command handling."""

    def _vtm_state(self) -> tuple[dict | None, dict | None]:
        """Return the current validated status and setting."""
        status = self.coordinator.data.get(self.vin, {}).get("vtmStatus")
        setting = get_vtm_setting(status)
        return (status, setting) if setting is not None else (None, None)

    @property
    def available(self) -> bool:
        """Return whether a usable refrigeration-box response is available."""
        return super().available and self._vtm_state()[1] is not None

    async def _async_write_vtm(
        self,
        *,
        temp: float | None = None,
        temp_mode: tuple[float, float, float] | None = None,
        duration: int | None = None,
        active: bool | None = None,
    ) -> None:
        """Merge one change into the latest VTM state and send it."""
        lock = self.coordinator.vtm_locks.setdefault(self.vin, asyncio.Lock())
        async with lock:
            vehicle = self.coordinator.get_vehicle_by_vin(self.vin)
            if vehicle is None:
                raise HomeAssistantError("Refrigeration box is unavailable")

            try:
                await self.coordinator.request_stats.async_inc_request()
                status = await self.hass.async_add_executor_job(
                    vehicle.get_vtm_status
                )
            except Exception as err:
                raise HomeAssistantError(
                    "Refrigeration box is unavailable"
                ) from err

            status = _merge_vtm_off_status(
                status,
                self.coordinator.data.get(self.vin, {}).get("vtmStatus"),
            )
            setting = _apply_vtm_pending(
                self.coordinator._vtm_pending,
                self.vin,
                status,
            )
            if setting is None or not isinstance(status, dict):
                raise HomeAssistantError("Refrigeration box is unavailable")
            if temp_mode is not None:
                minimum, maximum, default = temp_mode
                fresh_temp = float(setting["temp"])
                temp = fresh_temp if minimum <= fresh_temp <= maximum else default

            next_active = (
                status.get("activeStatus") == "1"
                if active is None
                else active
            )
            next_ts = str(status.get("vtmTsActive", "false")).lower()
            temp_value = (
                str(setting["temp"]) if temp is None else str(float(temp))
            )
            duration_value = str(
                int(float(setting["duration"]) if duration is None else duration)
            )
            command_setting = {
                "serviceParameters": [
                    {"key": "temp", "value": temp_value},
                    {"key": "duration", "value": duration_value},
                    {"key": "zaj.ts", "value": next_ts},
                ]
            }

            await self.coordinator.async_inc_invoke()
            try:
                success = await self.hass.async_add_executor_job(
                    vehicle.do_remote_control,
                    "start" if next_active else "stop",
                    "ZAJ",
                    command_setting,
                )
            except Exception as err:
                raise HomeAssistantError(
                    "Refrigeration-box command failed"
                ) from err
            if not success:
                raise HomeAssistantError("Refrigeration-box command failed")

            changes = {}
            if temp is not None:
                changes["temp"] = temp_value
            if duration is not None:
                changes["duration"] = duration_value
            if active is not None:
                changes["activeStatus"] = "1" if next_active else "0"
            deadline = monotonic() + VTM_SETTLE_SECONDS
            pending = self.coordinator._vtm_pending.setdefault(self.vin, {})
            for field, (value, _) in pending.items():
                pending[field] = (value, deadline)
            pending.update(
                (field, (value, deadline)) for field, value in changes.items()
            )
            setting["temp"] = temp_value
            setting["duration"] = duration_value
            status["vtmTsActive"] = next_ts
            status["activeStatus"] = "1" if next_active else "0"
            self.coordinator._cache_vtm_status(self.vin, status)
            self.coordinator.data.setdefault(self.vin, {})["vtmStatus"] = status
            self.coordinator._last_secondary.setdefault(self.vin, {})[
                "vtmStatus"
            ] = status
            self.coordinator._secondary_stale_count.pop(
                (self.vin, "vtmStatus"), None
            )
            self.async_write_ha_state()

            async def _reconcile() -> None:
                await asyncio.sleep(10)
                await self.coordinator.async_request_refresh()
                if pending := self.coordinator._vtm_pending.get(self.vin):
                    remaining = max(
                        deadline for _, deadline in pending.values()
                    ) - monotonic()
                    await asyncio.sleep(max(0, remaining))
                    await self.coordinator.async_request_refresh()

            if previous := self.coordinator._vtm_reconcile_tasks.get(self.vin):
                previous.cancel()
            task = self.coordinator.entry.async_create_background_task(
                self.hass,
                _reconcile(),
                f"Reconcile refrigeration box {self.vin}",
            )
            self.coordinator._vtm_reconcile_tasks[self.vin] = task
            task.add_done_callback(
                lambda done: self.coordinator._vtm_reconcile_tasks.pop(
                    self.vin, None
                )
                if self.coordinator._vtm_reconcile_tasks.get(self.vin) is done
                else None
            )
