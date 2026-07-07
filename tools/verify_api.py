#!/usr/bin/env python3
"""Verifikationstest gegen die echte Anlage – VOR der HA-Installation.

Läuft ohne installiertes Home Assistant: lädt api.py/const.py direkt,
ohne die __init__.py der Integration anzufassen.

Phase 1 (Standard): nur lesend – Teilbereiche, Störungen, offene Zonen.
Phase 2 (nur mit --test-schalten N): schaltet Teilbereich N scharf und
nach 5 Sekunden wieder unscharf. Nur ausführen, wenn das gerade
niemanden stört und keine Aufschaltung reagiert!

Aufruf (aus dem Projektordner heraus):
    python tools\verify_api.py --host 192.168.178.46 --user CODE --password PW
    python tools\verify_api.py --host ... --user ... --password ... --test-schalten 4
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import sys
import time
import types
from pathlib import Path

try:
    import httpx  # noqa: F401
except ImportError:
    sys.exit("Bitte zuerst: pip install httpx")

# ------------------------------------------------------------------ #
# api.py + const.py direkt laden (ohne __init__.py -> kein HA nötig) #
# ------------------------------------------------------------------ #
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


_load("const")
api = _load("api")
SecvestClient = api.SecvestClient


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--port", type=int, default=4433)
    ap.add_argument("--user", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument(
        "--test-schalten",
        type=int,
        metavar="N",
        help="Teilbereich N scharf und wieder unscharf schalten (VORSICHT)",
    )
    args = ap.parse_args()

    client = SecvestClient(args.host, args.port, args.user, args.password)
    try:
        print("== Phase 1: Lesen ==")
        data = await client.async_get_data()

        print("\nTeilbereiche:")
        for pid, part in sorted(data.partitions.items()):
            print(f"  {pid}: {part['name']:<14} -> {part['state']}")

        print(f"\nStörungen: {len(data.faults)}")
        for f in data.faults:
            ps = " [verhindert Scharfschalten]" if f.get("prevents-set") else ""
            print(f"  {f.get('ui-string', '?')}{ps}")

        print(f"\nOffene Zonen: {len(data.open_zones)}")
        for z in data.open_zones:
            print(f"  {z['name']} (Teilbereich {z['partitions']})")

        if args.test_schalten:
            n = args.test_schalten
            name = data.partitions.get(n, {}).get("name", f"#{n}")
            print(f"\n== Phase 2: Teilbereich {n} ({name}) schalten ==")
            input("Enter drücken zum Scharfschalten (Strg+C zum Abbruch)... ")
            result = await client.async_set_partition(n, "set")
            print(f"  Anlage meldet: {result.get('state')}")
            print("  Warte 5 Sekunden...")
            time.sleep(5)
            result = await client.async_set_partition(n, "unset")
            print(f"  Anlage meldet: {result.get('state')}")
            print("Schalttest abgeschlossen.")

        print("\nAlles OK – bereit für die Installation in Home Assistant.")
    finally:
        await client.async_close()


if __name__ == "__main__":
    asyncio.run(main())
