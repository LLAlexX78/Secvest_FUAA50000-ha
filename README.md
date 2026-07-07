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

## Entities

- **Alarm-Panel je Teilbereich** – scharf (extern), intern scharf
  (Anwesenheit, sofern der Teilbereich es unterstützt) und unscharf;
  Alarm wird als `triggered` angezeigt.
- **Binary Sensor je Zone/Melder** (`opening`) – offen/geschlossen.
- **Binary Sensor „Störung" je Teilbereich** (`problem`).
- **Binary Sensor „Wartung"** (`problem`) – anlagenweit, bei Funk-/
  Batterie- oder sonstigen Störungen.
- **Sensor „Letztes Ereignis"** – letzter Protokolleintrag inkl.
  Benutzer/Zeit; Attribut mit den letzten Ereignissen.

## Optionen

Unter **Konfigurieren** der Integration:

- **Abfrageintervall** (10–120 s, Standard 15 s). Nicht darunter – die
  Anlage bricht unter Last ab.
- **Genutzte Teilbereiche** – abwählen, was nicht gebraucht wird (z. B.
  ein leerer Teilbereich). Abgewählte Teilbereiche und deren Zonen
  erzeugen keine Entities.

## Beispiel-Automation (optional)

Benachrichtigung bei Wartungsbedarf (Entity-ID ggf. anpassen):

```yaml
automation:
  - alias: Secvest Wartung
    trigger:
      - platform: state
        entity_id: binary_sensor.abus_secvest_wartung
        to: "on"
    action:
      - service: notify.persistent_notification
        data:
          title: ABUS Secvest
          message: >-
            Wartung erforderlich:
            {{ state_attr('binary_sensor.abus_secvest_wartung', 'meldungen')
               | join(', ') }}
```

## Hinweis

Die genutzte REST/JSON-Schnittstelle ist **inoffiziell und
firmwareabhängig**. Sie wurde gegen die Firmware des Autors verifiziert
(Secvest FUAA50000, 07/2026) und kann auf anderen Firmware-Ständen
abweichen. Vor Inbetriebnahme mit `tools/verify_api.py` prüfen.
Bedienercode/Passwort niemals in Logs oder öffentliche Repos.

## Lizenz

[MIT](LICENSE) © 2026 Alexander Koenigs

