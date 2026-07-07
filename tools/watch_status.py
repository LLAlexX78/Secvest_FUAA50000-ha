#!/usr/bin/env python3
"""Nur-lesender Statusbeobachter für die Alarm-Recherche (Aufgabe 2).

Pollt sequentiell (NIE parallel) im einstellbaren Takt (Default 2 s):
    GET /system/partitions/
    GET /faults/
    GET /sec_global_status.cgx
und schreibt JEDE Änderung mit Zeitstempel nach watch_log.txt. So lässt
sich herausfinden, wie ein ausgelöster Alarm in welchem Endpoint als
welcher String erscheint (TRIGGERED-Erkennung).

WICHTIG (Grundregel/offener Punkt #5): Die Anlage bricht unter Last ab.
Deshalb strikt SEQUENTIELL und die Beobachtung kurz halten. Der 2-s-Takt
entspricht dem, was die Web-UI selbst tut. Bei Bedarf --interval erhöhen.
Das Skript schaltet NICHTS – reine GET-Abfragen.

Aufruf:
    python tools\\watch_status.py --host 192.168.178.46 --user CODE --password PW
    (dann Teilbereich scharf schalten, Alarm auslösen, quittieren; Strg+C)
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import sys
import types
from datetime import datetime
from pathlib import Path

try:
    import httpx  # noqa: F401
except ImportError:
    sys.exit("Bitte zuerst: pip install httpx")

PKG_DIR = Path(__file__).resolve().parent.parent / "custom_components" / "secvest"
if not PKG_DIR.exists():
    sys.exit(f"Ordner nicht gefunden: {PKG_DIR} – Skript aus dem Projektordner starten.")

_pkg = types.ModuleType("secvest_standalone")
_pkg.__path__ = [str(PKG_DIR)]
sys.modules["secvest_standalone"] = _pkg


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        f"secvest_standalone.{name}", PKG_DIR / f"{name}.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"secvest_standalone.{name}"] = mod
    spec.loader.exec_module(mod)
    return mod


const = _load("const")
api = _load("api")


ENDPOINTS = [
    ("partitions", const.ENDPOINT_PARTITIONS, "json"),
    ("faults", const.ENDPOINT_FAULTS, "json"),
    ("global_status", const.ENDPOINT_GLOBAL_STATUS, "text"),
]


async def _snapshot(client) -> dict:
    """Ein Durchlauf: alle Endpoints NACHEINANDER abfragen (roh)."""
    snap: dict = {}
    for key, path, kind in ENDPOINTS:
        try:
            resp = await client._request("GET", path)
            if resp.status_code >= 300:
                snap[key] = {"__http__": resp.status_code}
                continue
            if kind == "json":
                try:
                    snap[key] = resp.json()
                except ValueError:
                    snap[key] = {"__raw__": resp.text}
            else:
                snap[key] = resp.text
        except Exception as err:  # noqa: BLE001 – Beobachter darf nie crashen
            snap[key] = {"__error__": f"{type(err).__name__}: {err}"}
    return snap


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _write(logfile, line: str) -> None:
    with open(logfile, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    # Konsole tolerant gegenüber Zeichensatzproblemen halten
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", "replace").decode("ascii"))


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--port", type=int, default=const.DEFAULT_PORT)
    ap.add_argument("--user", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--interval", type=float, default=2.0,
                    help="Poll-Takt in Sekunden (Default 2.0; höher = schonender)")
    ap.add_argument("--logfile", default="watch_log.txt")
    args = ap.parse_args()

    client = api.SecvestClient(args.host, args.port, args.user, args.password)
    logfile = Path(args.logfile)

    _write(logfile, f"=== watch_status Start {_ts()} "
                    f"(Takt {args.interval}s, sequentiell) ===")
    prev: str | None = None
    cycle = 0
    try:
        while True:
            snap = await _snapshot(client)
            cur = json.dumps(snap, ensure_ascii=False, sort_keys=True)
            if cur != prev:
                _write(logfile, f"\n[{_ts()}] ÄNDERUNG:")
                _write(
                    logfile,
                    json.dumps(snap, ensure_ascii=False, indent=2, sort_keys=True),
                )
                prev = cur
            else:
                cycle += 1
                if cycle % 15 == 0:  # ~alle 30 s ein Lebenszeichen
                    _write(logfile, f"[{_ts()}] (unverändert)")
            await asyncio.sleep(args.interval)
    except KeyboardInterrupt:
        _write(logfile, f"\n=== watch_status Ende {_ts()} ===")
    finally:
        await client.async_close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
