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

## Installation über HACS

1. HACS → drei Punkte oben rechts → **Custom repositories**.
2. Repository `https://github.com/LLAlexX78/Secvest_FUAA50000-ha`,
   Kategorie **Integration** hinzufügen.
3. „ABUS Secvest" installieren, Home Assistant neu starten.
4. **Einstellungen → Geräte & Dienste → Integration hinzufügen** → „ABUS
   Secvest" → Host, Bedienercode und Web-Passwort eingeben.

Alternativ manuell: den Ordner `custom_components/secvest/` in das
HA-Konfigurationsverzeichnis kopieren und HA neu starten.

Mindestens Home Assistant **2024.5** erforderlich (`runtime_data`).

## Lizenz

[MIT](LICENSE) © 2026 Alexander Koenigs

