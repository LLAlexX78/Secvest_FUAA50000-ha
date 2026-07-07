# ABUS Secvest FUAA50000 – Home Assistant Integration

Custom Component für die ABUS Secvest über deren inoffizielle
REST/JSON-Schnittstelle (HTTPS + HTTP Basic Auth mit Form-Login-
Fallback, lokales Polling).

**Status: API gegen echte Anlage verifiziert** (07/2026) – Lesen der
Teilbereiche/Störungen/Zonen sowie set→unset-Schalten per PUT bestätigt.
Details und offene Punkte in `CLAUDE.md`. Vor Inbetriebnahme die
Endpoints gegen die eigene Firmware prüfen:

```
python tools/verify_api.py --host <IP> --user <Bedienercode> --password <PW>
```

## Struktur

```
custom_components/secvest/
├── __init__.py             Setup/Teardown, Plattform-Forwarding
├── api.py                  httpx-Client (Basic Auth + Form-Login, Parser)
├── config_flow.py          UI-Einrichtung
├── coordinator.py          Polling (DataUpdateCoordinator)
├── alarm_control_panel.py  Partition(en) als Alarmpanel
├── binary_sensor.py        Zonen/Melder
├── const.py                Endpoints & Mapping (HIER anpassen)
├── manifest.json
└── translations/           de + en
tools/verify_api.py         Verifikationstest gegen die Anlage (Lesen; optional Schalttest)
CLAUDE.md                   Arbeitsplan für Claude Code
```
