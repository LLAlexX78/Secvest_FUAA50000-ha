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
    entities: list[BinarySensorEntity] = [
        SecvestFaultSensor(coordinator, entry, pid)
        for pid in sorted(coordinator.data.partitions)
    ]
    entities += [
        SecvestZoneSensor(coordinator, entry, zid)
        for zid in sorted(coordinator.data.zones)
    ]
    async_add_entities(entities)


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


class SecvestZoneSensor(CoordinatorEntity[SecvestCoordinator], BinarySensorEntity):
    """Einzelner Melder/eine Zone (offen/geschlossen).

    Offen = die Zone erscheint als offene-Zone-Störung (type 5000).
    Name wird beim ersten Offen-Zustand aus der Störung übernommen und
    im Client gecacht; bis dahin "Zone <id>". unique_id über die
    stabile Zonen-ID, nicht den Namen.
    """

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.OPENING

    def __init__(
        self,
        coordinator: SecvestCoordinator,
        entry: SecvestConfigEntry,
        zone_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._zone = str(zone_id)
        self._attr_unique_id = f"{entry.entry_id}_zone_{self._zone}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
        )

    def _zone_data(self) -> dict[str, Any]:
        return self.coordinator.data.zones.get(self._zone, {})

    @property
    def name(self) -> str:
        return self._zone_data().get("name") or f"Zone {self._zone}"

    @property
    def is_on(self) -> bool:
        return bool(self._zone_data().get("open"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        zone = self._zone_data()
        return {
            "zone_id": self._zone,
            "teilbereich": zone.get("partition"),
        }
