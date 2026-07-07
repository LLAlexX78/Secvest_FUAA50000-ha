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

## Offene Punkte

1. ~~PUT mit Basic Auth verifizieren~~ **ERLEDIGT (07.07.2026)**: Der PUT
   wurde direkt via Basic akzeptiert und fachlich verarbeitet (HTTP 409,
   nicht 401/403). Der Form-Login-Fallback musste nicht greifen – Basic
   funktioniert auch schreibend.
2. ~~"partset" (intern scharf) verifizieren~~ **ERLEDIGT (07.07.2026)**:
   Auf TB1 bestätigt (String `partset`), ARM_HOME freigeschaltet. Feature
   ist partitionsabhängig – nicht-fähige Teilbereiche liefern 409 (TB3).
   Siehe partset-Test oben.
3. ~~Echter set→unset-Toggle~~ **ERLEDIGT (07.07.2026)**: Auf TB3 (OG)
   sauber durchgeführt – `set` und `unset` je von der Anlage bestätigt.
   Merke: 409 = prevents-set / offene Zone / **leerer Teilbereich**, nie
   Auth. Für künftige Schalttests einen Teilbereich MIT Zone nehmen
   (nicht TB4).
4. /faults/ liefert sporadisch 404 (im HAR belegt; am 07.07. lieferte es
   sauber) – Client behandelt das bereits als optional. Nicht als Fehler
   werten.
5. Die Anlage bricht unter Last Requests ab (Status 0 im HAR) –
   Polling nicht unter 10 s stellen, keine parallelen Abfragen. Zusätzlich
   TLS-Handshake ~7 s einplanen (siehe Connect-Timeout-Fix oben).
6. pytest mit pytest-homeassistant-custom-component aufsetzen;
   Fixtures aus den HAR-Payloads bauen (liegen in diesem Repo NICHT –
   Zugangsdaten! Payload-Beispiele stehen oben).

## Ausbau (nach Inbetriebnahme)

- sensor.py: letzter Log-Eintrag aus /logs/, Firmware-Info
- Options Flow: Scan-Intervall einstellbar
- Reauth-Flow
- HACS-Struktur (hacs.json, Releases)

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
