# Projekt: ABUS Secvest FUAA50000 → Home Assistant Integration

## Status: API VERIFIZIERT (07.07.2026, HAR-Mitschnitt der Web-UI)

Die Endpoints sind keine Vermutungen mehr, sondern per Mitschnitt belegt:

| Funktion   | Request                              | Payload/Antwort |
|------------|--------------------------------------|-----------------|
| Status     | GET /system/partitions/              | JSON-Array: id, name, state ("set"/"unset"), zones |
| Schalten   | PUT /system/partitions-{n}/          | Body {"state":"set"|"unset"}, Antwort = neuer Zustand |
| Störungen  | GET /faults/                         | JSON: ui-string, affects-partition, prevents-set |
| Off. Zonen | GET /sec_global_status.cgx           | XML-artig: <zone><name>..<state>..<partitions>.. |
| Logs       | GET /logs/                           | JSON |
| Login      | POST /sec_login.cgi (usr=..&pwd=..)  | Form-Login, Session-Cookie (Fallback) |

Auth: HTTP **Basic** funktioniert direkt auf den REST-Endpoints
(verifiziert per Probe-Skript). Der Client nutzt Basic primär und
fällt bei 401/403 automatisch auf den Form-Login zurück.

Beispielanlage: 4 Teilbereiche ("Haustür", "EG", "OG", "Teilber. 4"),
Draht-Zonen 301-303. Unscharfschalten per API funktioniert (2x belegt).

## Live-Test 07.07.2026 (tools/verify_api.py gegen die Anlage)

Lesen (Phase 1) erfolgreich: 4 Teilbereiche (Haustür/EG/OG/Teilber. 4),
alle `unset`; 0 offene Zonen; 2 Störungen mit `prevents-set`
("Z301 A EG Draht", "Z302 A OG Draht"). /faults/ und
sec_global_status.cgx lieferten diesmal sauber (kein 404).

Zonen-Zuordnung (aus /system/partitions/): TB1 Haustür → Z303,
TB2 EG → Z301, TB3 OG → Z302, **TB4 Teilber. 4 → keine Zone (`[]`)**.

Schalttest TB4 (leer): PUT `set` → **HTTP 409**, und zwar auch nachdem
die Störungen weg waren (Störungen 0, offene Zonen 0). Damit belegt:
**ein leerer Teilbereich ist nicht scharfschaltbar** – die CLAUDE.md-
Annahme "TB4 leer -> ideal für den Schalttest" war falsch. Für echte
Schalttests einen Teilbereich mit Zone nehmen.

Echter Toggle TB3 (OG, Z302): PUT `set` → Anlage meldet `set`, nach 5 s
PUT `unset` → Anlage meldet `unset`. **Vollständiger set→unset-Zyklus
per PUT/Basic-Auth verifiziert.** Anschließende Leseabfrage: alles wieder
`unset`, 0 Störungen. (Vorheriger 409 auf TB4 kam von der fehlenden Zone,
nicht von den zwischenzeitlichen prevents-set-Störungen.)

**Connect-Timeout-Fix**: Der TLS-Handshake der Anlage dauert gemessen
~6,8 s (ECDHE-RSA-CHACHA20/TLSv1.2, schwache Panel-CPU). Der alte
`connect=5.0` führte reproduzierbar zu ConnectTimeout. In api.py auf
`connect=20.0` angehoben.

## partset-Test 07.07.2026 (Aufgabe 1) – VERIFIZIERT

`tools/verify_api.py --test-partset N` ergänzt (PUT `{"state":"partset"}`,
Kontroll-Read, dann unset). Zwei Tests mit Freigabe:

- **TB3 (OG): HTTP 409** – trotz 0 Störungen/0 offene Zonen und obwohl
  `set` dort funktioniert.
- **TB1 (Haustür): ERFOLG.** PUT `partset` → Antwort
  `{'id':'1','name':'Haustür','state':'partset','zones':['303']}`;
  `GET /system/partitions/` meldet ebenfalls `state: 'partset'`; danach
  `unset` sauber.

**Fazit: partset wird unterstützt, exakter Zustandsstring = `partset`
(in PUT-Antwort UND GET bestätigt) – aber PARTITIONSABHÄNGIG:** nur
intern-scharf-fähige Teilbereiche akzeptieren es (TB1 ja, TB3 nein/409).

**Umgesetzt (Aufgabe-1-Schritt 3):** ARM_HOME in
`alarm_control_panel.py` freigeschaltet (`ARM_AWAY | ARM_HOME`),
`async_alarm_arm_home` → `partset`, Mapping `partset` →
`ARMED_HOME`, `STATE_PARTSET` in const.py als verifiziert markiert.
Auf nicht-fähigen Teilbereichen führt ARM_HOME zu HTTP 409, das als
HomeAssistantError sichtbar wird.

## Testalarm 07.07.2026 (Aufgabe 2) – TRIGGERED verifiziert

Mitschnitt per `tools/watch_status.py` (2-s-Takt, sequentiell) während
eines echten Testalarms auf TB2 (EG, Z301). Beobachtete state-Übergänge
des Teilbereichs in `GET /system/partitions/`:

  set → **set-alarm** (Vollalarm) → **acknowledged** (quittiert, nicht
  zurückgesetzt) → unset

**Kernbefund: Der Alarm erscheint AUSSCHLIESSLICH im `state`-Feld von
`/system/partitions/`.** `/faults/` blieb `[]`, `sec_global_status.cgx`
`open_zones` blieb leer. Exakte Strings:
- `set-alarm` = ausgelöster Alarm → HA `TRIGGERED`
- `acknowledged` = Alarm quittiert, aber noch nicht zurückgesetzt →
  ebenfalls HA `TRIGGERED` (Alarm bleibt „im Speicher" bis Reset).

**Umgesetzt (Aufgabe-2-Schritt 4):** const.py `STATE_ALARM`/
`STATE_ACKNOWLEDGED`; alarm_control_panel.py mappt beide (plus generisch
alles mit „alarm" im String) auf `AlarmControlPanelState.TRIGGERED`;
roher Panel-`state` zusätzlich als Attribut `panel_state`. Kein neuer
Endpoint/keine SecvestData-Erweiterung nötig – der state trägt alles.

## /logs/-Struktur 07.07.2026 (Aufgabe 3) – verifiziert

`GET /logs/` → JSON-Liste, **neueste zuerst**, **~600 Einträge**;
**`?limit=N` wird IGNORIERT** (immer alle) → client-seitig kürzen.
Eintragsschema:

```json
{ "id": "456555213824", "type": "normal" | "alarm",
  "desc": "Ben 001 TB 2 rückgesetzt",
  "events": [ { "timestamp": "1783418804", "partition": "1",
                "user": "1", "username": "Alex", "zone": "301" } ] }
```

Felder: `desc` = Klartext, `type` = normal/alarm; in `events[0]`:
`timestamp` (Unix-Epoch als String), `username`/`user`, optional
`partition`/`zone`. Achtung: `partition` im Event ist 0-basiert
(TB2 → "1"), der `desc`-Text 1-basiert ("TB 2"). Zeit-Caveat: Epoch
scheint Lokalzeit-als-UTC zu sein (Log 12:06 vs. PC 10:06 beim Test) –
Zeitzone ggf. später glätten.

**Umgesetzt (Aufgabe-3):** api.py `async_get_logs(limit=10)` +
`SecvestData.logs`, im selben Poll-Zyklus (4. sequentieller GET,
optional/resilient). Neue `sensor.py`: Sensor „Letztes Ereignis"
(State = `desc` des neuesten Eintrags; Attribute typ/zeit/benutzer/
teilbereich/zone + `letzte_ereignisse`-Liste). Platform.SENSOR in
__init__.py registriert. Lastnotiz: 600er-Payload je Poll – falls die
Anlage darunter leidet, Logs später seltener holen (nicht jeder Zyklus).

## Zonen 07.07.2026 (Aufgabe 4) – GELÖST über /faults/ type 5000

Endpoint-Suche zeigte: REST-Zonendetails gibt es nicht
(`/system/zones/`, `/system/zones-301/`, `/zones-301/` … alle 404).
`sec_global_status.cgx` und `sec_zones.cgx` liefern Volldaten nur einer
eingeloggten Web-UI-Session – mit Basic Auth kommt nur das Skelett
(`<authorised></authorised>`, leere open_zones), **auch wenn eine Zone
offen ist** (live geprüft). Der Form-Login (`POST /sec_login.cgi`
usr/pwd) stellt KEINE Session her (kein Set-Cookie, Antwort = Login-HTML)
→ die `_form_login`-Fallback-Logik ist de facto wirkungslos; Basic reicht
aber für alle genutzten REST-Endpoints.

**Basic-taugliche Lösung:** Eine OFFENE Zone erscheint in `/faults/` als

```json
{ "type": "5000", "ui-string": "Z302 A OG Draht",
  "affects-partition": ["3"], "affects-zone": "302",
  "prevents-set": true, "is-rf-warning": false }
```

- Offen/Zu: Zone ist offen, wenn eine `type:"5000"`-Störung ihre ID in
  `affects-zone` trägt.
- ID = `affects-zone` (`"302"`), Teilbereich = `affects-partition`
  (sauber 1-basiert `["3"]`), Name = `ui-string` (Prefix „Z302 A "
  entfernt → „OG Draht"). Zonen-Grundgerüst (alle IDs + Teilbereich)
  aus `/system/partitions/`.

Merke: In `sec_global_status.cgx` ist `<partitions>` eine Bitmaske
(TB3 → 4), in `/faults/` `affects-partition` dagegen die klare Liste
(`["3"]`) – wir nutzen /faults/.

**Umgesetzt (Aufgabe 4):** api.py `_build_zones()` + `SecvestData.zones`
(zone_id → name/partition/open); Namen-Cache im Client (Name nur bei
offener Zone sichtbar → einmal gesehen für Laufzeit gemerkt).
sec_global_status-Abruf ENTFERNT (unter Basic tot → ein GET/Poll
weniger). binary_sensor.py: `SecvestZoneSensor` je Zone
(device_class opening, unique_id über Zonen-ID). alarm_control_panel.py
open_zones-Attribut nutzt jetzt data.zones (Bitmaske-Bug behoben).
const.py `FAULT_TYPE_OPEN_ZONE="5000"`. End-to-End verifiziert (302 offen
= „OG Draht"/TB3). Namens-Caveat: geschlossene, nie geöffnete Zonen
heißen „Zone <id>" bis zum ersten Offen-Zustand (in HA umbenennbar).

## Wartung/Störungen (Aufgabe 5) – 07.07.2026

/faults/-Felder: `type`, `id`, `ui-string`, `affects-partition` (Liste),
`affects-zone`, `prevents-set`, `prevents-reset`, `is-rf-warning`.
Bekannte type-Codes: **5000 = offene Zone**. Batterie-/Funk-Codes bisher
nicht aufgetreten (nicht provozierbar) → sobald sie erscheinen, in
`const.FAULT_TYPES` eintragen.

**Umgesetzt:** const.py `FAULT_TYPES` (Code→Klartext, erweiterbar).
binary_sensor.py `SecvestMaintenanceSensor` (anlagenweit, device_class
problem): „Ein" bei `is-rf-warning` ODER jeder Störung ≠ 5000 (unbekannte
Codes generisch sichtbar; offene Zonen ausgeschlossen, die decken die
Zonen-Sensoren ab). Attribute: meldungen, funkwarnung, details
(text/typ/is_rf_warning/prevents_set). Verifiziert: bei leerem /faults/
zeigt der Sensor „aus".

## Status Aufgaben 1–6

Alle Aufgaben aus AUFGABEN.md umgesetzt und (soweit ohne HA möglich)
verifiziert: ARM_HOME/partset, TRIGGERED, Logs-Sensor, Zonen-Sensoren,
Wartungssensor, Options-Flow (Intervall + Teilbereich-Auswahl),
Reauth-Flow, pytest (CI grün). Offen bleiben nur die HA-UI-Abnahmen
(Test in der laufenden HA-Instanz) sowie die Punkte unten.

## Bekannte Einschränkungen / offen

- **/faults/** liefert sporadisch 404 – Client behandelt das optional,
  nicht als Fehler werten.
- **Last**: Anlage bricht unter Last ab. Polling nie < 10 s, keine
  parallelen Abfragen, TLS-Handshake ~7 s einplanen.
- **Batterie-/Funk-Störungscodes** noch unbekannt (nicht provozierbar) –
  bei Auftreten in `const.FAULT_TYPES` eintragen; der Wartungssensor
  zeigt sie schon generisch.
- **Zonennamen** geschlossener, nie geöffneter Zonen sind generisch
  („Zone <id>") bis zum ersten Offen-Zustand (in HA umbenennbar).
- **Log-Zeit** ist Epoch als Lokalzeit-als-UTC – Zeitzone ggf. glätten.
- **Form-Login** (`sec_login.cgi`) stellt keine Session her → die
  `.cgx`-Volldaten (nur Web-UI-Session) sind nicht nutzbar. Basic reicht
  für alle genutzten REST-Endpoints; Zonen laufen über /faults/.

## Nach Abschluss – Erinnerungen

- **Passwort der Anlage wechseln** – es wurde im Chatverlauf geteilt.
- Lokale `.claude/settings*.json` enthalten das Passwort im Klartext
  (per `.gitignore` NICHT im Repo, aber lokal auf der Platte) – bei
  Bedarf bereinigen.
- Keine HAR-/Log-Datei ins Repo (Zugangsdaten; `watch_log.txt` ist
  gitignored). Payload-Beispiele stehen in dieser Datei.

## Regeln

- Bedienercode/Passwort niemals loggen oder committen.
- Schaltbefehle nie in automatisierten Tests gegen die echte Anlage.
- HA-Konventionen: async, DataUpdateCoordinator, runtime_data,
  has_entity_name, unique_id pro Entity.

## Test-Reihenfolge

1. `python tools\verify_api.py --host <IP> --user <code> --password <pw>`
2. Wenn Lesen ok: `--test-schalten 4` (Teilbereich 4 ist leer -> ideal)
3. custom_components/secvest/ in HA-Config kopieren, HA neu starten
4. Integration über UI hinzufügen
