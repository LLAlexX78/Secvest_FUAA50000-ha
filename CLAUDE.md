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

## Offene Punkte

1. ~~PUT mit Basic Auth verifizieren~~ **ERLEDIGT (07.07.2026)**: Der PUT
   wurde direkt via Basic akzeptiert und fachlich verarbeitet (HTTP 409,
   nicht 401/403). Der Form-Login-Fallback musste nicht greifen – Basic
   funktioniert auch schreibend.
2. **"partset"** (intern scharf) ist unverifiziert – erst testen,
   dann ggf. ARM_HOME im Panel freischalten.
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
