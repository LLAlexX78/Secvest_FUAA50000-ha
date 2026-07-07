"""Sensor: Letztes Ereignis aus dem Secvest-Ereignisprotokoll (/logs/).

State = Kurztext des neuesten Ereignisses. Attribute: Zeitstempel,
Benutzer, Typ und die letzten Ereignisse als Liste.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SecvestConfigEntry
from .const import DOMAIN
from .coordinator import SecvestCoordinator

# HA begrenzt den State auf 255 Zeichen.
_MAX_STATE_LEN = 255


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SecvestConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([SecvestLastEventSensor(coordinator, entry)])


def _first_event(entry: dict[str, Any]) -> dict[str, Any]:
    """events[] enthält (mind.) einen Eintrag mit Zeit/Benutzer/Zone."""
    events = entry.get("events") or [{}]
    return events[0] if events else {}


def _iso(timestamp: Any) -> str | None:
    """Unix-Epoch (String/Zahl) -> ISO-Zeit; None bei Unparsbarem."""
    try:
        return datetime.fromtimestamp(int(timestamp)).isoformat()
    except (TypeError, ValueError):
        return None


class SecvestLastEventSensor(
    CoordinatorEntity[SecvestCoordinator], SensorEntity
):
    """Zeigt das neueste Ereignis aus dem Anlagen-Protokoll."""

    _attr_has_entity_name = True
    _attr_name = "Letztes Ereignis"
    _attr_icon = "mdi:history"

    def __init__(
        self, coordinator: SecvestCoordinator, entry: SecvestConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_last_event"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
        )

    def _logs(self) -> list[dict[str, Any]]:
        return self.coordinator.data.logs

    @property
    def native_value(self) -> str | None:
        logs = self._logs()
        if not logs:
            return None
        return (logs[0].get("desc") or "")[:_MAX_STATE_LEN] or None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        logs = self._logs()
        if not logs:
            return {}
        newest = logs[0]
        ev = _first_event(newest)
        return {
            "typ": newest.get("type"),
            "zeit": _iso(ev.get("timestamp")),
            "timestamp": ev.get("timestamp"),
            "benutzer": ev.get("username") or ev.get("user"),
            "teilbereich": ev.get("partition"),
            "zone": ev.get("zone"),
            "letzte_ereignisse": [
                {
                    "zeit": _iso(_first_event(e).get("timestamp")),
                    "text": e.get("desc"),
                    "typ": e.get("type"),
                    "benutzer": (
                        _first_event(e).get("username")
                        or _first_event(e).get("user")
                    ),
                }
                for e in logs
            ],
        }
