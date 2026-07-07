"""Alarm-Panel-Entities: eine pro Secvest-Teilbereich.

Nutzt die echten Namen aus der Anlage (z.B. "Haustür", "EG", "OG").
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SecvestConfigEntry
from .api import SecvestError
from .const import DOMAIN, STATE_SET, STATE_UNSET
from .coordinator import SecvestCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SecvestConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        SecvestAlarmPanel(coordinator, entry, pid)
        for pid in sorted(coordinator.data.partitions)
    )


class SecvestAlarmPanel(CoordinatorEntity[SecvestCoordinator], AlarmControlPanelEntity):
    """Ein Teilbereich der Secvest als Alarmpanel."""

    _attr_has_entity_name = True
    _attr_supported_features = AlarmControlPanelEntityFeature.ARM_AWAY
    _attr_code_arm_required = False

    def __init__(
        self,
        coordinator: SecvestCoordinator,
        entry: SecvestConfigEntry,
        partition: int,
    ) -> None:
        super().__init__(coordinator)
        self._partition = partition
        self._attr_unique_id = f"{entry.entry_id}_partition_{partition}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="ABUS Secvest",
            manufacturer="ABUS",
            model="Secvest FUAA50000",
        )

    def _data(self) -> dict[str, Any] | None:
        return self.coordinator.data.partitions.get(self._partition)

    @property
    def name(self) -> str:
        part = self._data()
        return part["name"] if part else f"Teilbereich {self._partition}"

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        part = self._data()
        if not part:
            return None
        if part["state"] == STATE_SET:
            return AlarmControlPanelState.ARMED_AWAY
        if part["state"] == STATE_UNSET:
            return AlarmControlPanelState.DISARMED
        if part["state"].startswith("part"):
            return AlarmControlPanelState.ARMED_HOME
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Störungen und offene Zonen dieses Teilbereichs anzeigen."""
        pid = str(self._partition)
        faults = [
            f.get("ui-string", "?")
            for f in self.coordinator.data.faults
            if pid in f.get("affects-partition", [])
        ]
        prevents_set = any(
            f.get("prevents-set")
            for f in self.coordinator.data.faults
            if pid in f.get("affects-partition", [])
        )
        open_zones = [
            z["name"]
            for z in self.coordinator.data.open_zones
            if pid in z.get("partitions", "")
        ]
        return {
            "faults": faults,
            "prevents_set": prevents_set,
            "open_zones": open_zones,
        }

    async def _switch(self, mode: str) -> None:
        try:
            await self.coordinator.client.async_set_partition(
                self._partition, mode
            )
        except SecvestError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        await self._switch(STATE_SET)

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        await self._switch(STATE_UNSET)
