"""Binary Sensors: Störungsstatus pro Teilbereich.

"Ein" bedeutet: mindestens eine Störung betrifft diesen Teilbereich
(z.B. offene Draht-Zone), die das Scharfschalten verhindern kann.
Details stehen in den Attributen.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SecvestConfigEntry
from .const import DOMAIN
from .coordinator import SecvestCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SecvestConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        SecvestFaultSensor(coordinator, entry, pid)
        for pid in sorted(coordinator.data.partitions)
    )


class SecvestFaultSensor(CoordinatorEntity[SecvestCoordinator], BinarySensorEntity):
    """Störungssensor eines Teilbereichs."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        coordinator: SecvestCoordinator,
        entry: SecvestConfigEntry,
        partition: int,
    ) -> None:
        super().__init__(coordinator)
        self._partition = partition
        self._attr_unique_id = f"{entry.entry_id}_fault_{partition}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
        )

    @property
    def name(self) -> str:
        part = self.coordinator.data.partitions.get(self._partition)
        base = part["name"] if part else f"Teilbereich {self._partition}"
        return f"Störung {base}"

    def _faults(self) -> list[dict[str, Any]]:
        pid = str(self._partition)
        return [
            f
            for f in self.coordinator.data.faults
            if pid in f.get("affects-partition", [])
        ]

    @property
    def is_on(self) -> bool:
        return len(self._faults()) > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        faults = self._faults()
        return {
            "meldungen": [f.get("ui-string", "?") for f in faults],
            "verhindert_scharfschalten": any(
                f.get("prevents-set") for f in faults
            ),
        }
