"""Async API-Client für die ABUS Secvest (FUAA50000).

Auf Basis eines HAR-Mitschnitts der Web-UI verifiziert (07/2026).
Primär HTTP Basic Auth; falls die Anlage einen Request mit 401/403
ablehnt, wird automatisch der Form-Login (/sec_login.cgi) als
Session-Fallback ausgeführt und der Request wiederholt.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from .const import (
    DEFAULT_LOG_LIMIT,
    ENDPOINT_FAULTS,
    ENDPOINT_FORM_LOGIN,
    ENDPOINT_GLOBAL_STATUS,
    ENDPOINT_LOGS,
    ENDPOINT_PARTITION_SET,
    ENDPOINT_PARTITIONS,
    STATE_SET,
    STATE_UNSET,
)

_LOGGER = logging.getLogger(__name__)

# Der TLS-Handshake der Anlage dauert gemessen ~7 s (schwache Panel-CPU,
# ECDHE-RSA-CHACHA20/TLSv1.2). Connect-Timeout entsprechend großzügig.
TIMEOUT = httpx.Timeout(10.0, connect=20.0)

_ZONE_RE = re.compile(
    r"<zone><name>(?P<name>.*?)</name><state>(?P<state>.*?)</state>"
    r"<partitions>(?P<partitions>.*?)</partitions></zone>",
    re.DOTALL,
)


class SecvestError(Exception):
    """Basisfehler."""


class SecvestAuthError(SecvestError):
    """Anmeldung fehlgeschlagen."""


class SecvestConnectionError(SecvestError):
    """Anlage nicht erreichbar."""


@dataclass
class SecvestData:
    """Normalisierter Zustand der Anlage."""

    # partition_id -> {"name": str, "state": "set"/"unset", "zones": [str]}
    partitions: dict[int, dict[str, Any]] = field(default_factory=dict)
    # Störungen aus /faults/ (inkl. prevents-set)
    faults: list[dict[str, Any]] = field(default_factory=list)
    # Offene Zonen aus sec_global_status: [{"name", "state", "partitions"}]
    open_zones: list[dict[str, str]] = field(default_factory=list)
    # Neueste Ereignisse aus /logs/ (client-seitig begrenzt)
    logs: list[dict[str, Any]] = field(default_factory=list)


class SecvestClient:
    """Client für die Secvest-REST-Schnittstelle."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        verify_ssl: bool = False,
    ) -> None:
        self._base = f"https://{host}:{port}"
        self._username = username
        self._password = password
        self._client = httpx.AsyncClient(
            auth=httpx.BasicAuth(username, password),
            verify=verify_ssl,
            timeout=TIMEOUT,
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        self._form_login_done = False

    async def async_close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------ #
    # Low-level mit Auth-Fallback                                        #
    # ------------------------------------------------------------------ #

    async def _form_login(self) -> None:
        """Session-Login wie die Web-UI: POST usr/pwd, Cookie im Client."""
        try:
            resp = await self._client.post(
                self._base + ENDPOINT_FORM_LOGIN,
                data={"usr": self._username, "pwd": self._password},
            )
        except httpx.HTTPError as err:
            raise SecvestConnectionError("Form-Login nicht erreichbar") from err
        if resp.status_code >= 400:
            raise SecvestAuthError(
                f"Form-Login abgelehnt (HTTP {resp.status_code})"
            )
        self._form_login_done = True
        _LOGGER.debug("Form-Login als Session-Fallback ausgeführt")

    async def _request(
        self, method: str, path: str, **kwargs: Any
    ) -> httpx.Response:
        try:
            resp = await self._client.request(method, self._base + path, **kwargs)
        except httpx.ConnectError as err:
            raise SecvestConnectionError(
                f"Keine Verbindung zu {self._base}"
            ) from err
        except httpx.TimeoutException as err:
            raise SecvestConnectionError("Timeout") from err

        # Basic abgelehnt? Einmalig Session-Login versuchen und wiederholen.
        if resp.status_code in (401, 403) and not self._form_login_done:
            await self._form_login()
            try:
                resp = await self._client.request(
                    method, self._base + path, **kwargs
                )
            except httpx.HTTPError as err:
                raise SecvestConnectionError("Wiederholung fehlgeschlagen") from err

        if resp.status_code in (401, 403):
            raise SecvestAuthError(
                "Anmeldung abgelehnt – Benutzer Code / Web-Passwort prüfen"
            )
        return resp

    # ------------------------------------------------------------------ #
    # High-level                                                         #
    # ------------------------------------------------------------------ #

    async def async_validate(self) -> None:
        """Für den Config Flow: erreichbar + Auth ok?"""
        resp = await self._request("GET", ENDPOINT_PARTITIONS)
        if resp.status_code >= 300:
            raise SecvestConnectionError(
                f"Unerwartete Antwort: HTTP {resp.status_code}"
            )
        try:
            resp.json()
        except ValueError as err:
            raise SecvestConnectionError(
                "Antwort ist kein JSON – Firmware abweichend?"
            ) from err

    async def async_get_data(self) -> SecvestData:
        """Teilbereiche, Störungen und offene Zonen abholen."""
        data = SecvestData()

        # Teilbereiche (Pflicht)
        resp = await self._request("GET", ENDPOINT_PARTITIONS)
        if resp.status_code >= 300:
            raise SecvestConnectionError(
                f"Partitionsstatus fehlgeschlagen: HTTP {resp.status_code}"
            )
        for part in resp.json():
            try:
                pid = int(part["id"])
            except (KeyError, TypeError, ValueError):
                continue
            data.partitions[pid] = {
                "name": part.get("name", f"Teilbereich {pid}"),
                "state": str(part.get("state", "")).lower(),
                "zones": part.get("zones", []),
            }

        # Störungen (optional – die Anlage liefert hier gelegentlich 404)
        try:
            resp = await self._request("GET", ENDPOINT_FAULTS)
            if resp.status_code < 300:
                data.faults = resp.json()
        except (SecvestConnectionError, ValueError):
            _LOGGER.debug("Faults nicht abrufbar, wird übersprungen")

        # Offene Zonen (optional, XML-artiges Format)
        try:
            resp = await self._request("GET", ENDPOINT_GLOBAL_STATUS)
            if resp.status_code < 300:
                data.open_zones = [
                    m.groupdict() for m in _ZONE_RE.finditer(resp.text)
                ]
        except SecvestConnectionError:
            _LOGGER.debug("Global-Status nicht abrufbar, wird übersprungen")

        # Ereignisprotokoll (optional). Im selben sequentiellen Poll-Zyklus,
        # keine Extra-Requests außerhalb des Coordinators.
        try:
            data.logs = await self.async_get_logs()
        except SecvestConnectionError:
            _LOGGER.debug("Logs nicht abrufbar, werden übersprungen")

        return data

    async def async_get_logs(self, limit: int = DEFAULT_LOG_LIMIT) -> list[dict]:
        """Neueste Ereignisse aus /logs/.

        Die Anlage ignoriert ?limit und liefert immer alle (~600 Einträge,
        neueste zuerst); daher client-seitig auf die neuesten kürzen.
        """
        resp = await self._request("GET", ENDPOINT_LOGS)
        if resp.status_code >= 300:
            return []
        try:
            data = resp.json()
        except ValueError:
            return []
        if not isinstance(data, list):
            return []
        return data[:limit]

    async def async_set_partition(self, partition: int, mode: str) -> dict:
        """Teilbereich schalten.

        mode: "set" | "unset" (verifiziert) | "partset" (unverifiziert).
        Rückgabe: der von der Anlage bestätigte neue Zustand.
        """
        if mode not in (STATE_SET, STATE_UNSET, "partset"):
            raise ValueError(f"Ungültiger Modus: {mode}")
        path = ENDPOINT_PARTITION_SET.format(p=partition)
        resp = await self._request("PUT", path, json={"state": mode})
        if resp.status_code >= 300:
            raise SecvestError(
                f"Schalten fehlgeschlagen: HTTP {resp.status_code} – "
                "mögliche Ursache: Störung mit prevents-set oder offene Zone"
            )
        try:
            return resp.json()
        except ValueError:
            return {}
