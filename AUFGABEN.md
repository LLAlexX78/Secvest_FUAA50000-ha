# AUFGABEN.md — Ausbauplan Secvest-Integration

Arbeitsanweisung für Claude Code. Aufgaben strikt in dieser Reihenfolge
abarbeiten, eine nach der anderen. Nach jeder Aufgabe: Git-Commit,
CLAUDE.md aktualisieren (Status + neue Erkenntnisse), kurzer Bericht an
den Nutzer, dann auf Freigabe für die nächste Aufgabe warten.

## Grundregeln (gelten für alle Aufgaben)

- Schaltbefehle (PUT auf partitions) NIEMALS ohne ausdrückliche Freigabe
  des Nutzers im Chat ausführen. Testobjekt ist immer Teilbereich 4
  ("Teilber. 4", keine Zonen zugeordnet) — nie Teilbereich 1-3.
- Neue Endpoints nie raten: erst per lesendem Testaufruf oder
  DevTools-Mitschnitt des Nutzers verifizieren, reale Payload in der
  CLAUDE.md dokumentieren, dann implementieren.
- Zugangsdaten niemals in Dateien, Commits oder Logs.
- Nach jeder Code-Änderung: python -m py_compile über alle geänderten
  Dateien; wenn pytest eingerichtet ist (Aufgabe 7), Tests laufen lassen.
- Die Anlage bricht unter Last Requests ab: keine parallelen Abfragen,
  Polling-Intervall nie unter 10 s.

---

## Aufgabe 1: "partset" (intern scharf) verifizieren und freischalten

Ziel: ARM_HOME im Alarmpanel funktionsfähig machen.

1. Verifikationsschritt vorbereiten: tools/verify_api.py um eine Option
   --test-partset N erweitern (PUT {"state":"partset"}, nach 5 s unset).
2. Nutzer bitten, den Test gegen Teilbereich 4 auszuführen, Ausgabe
   auswerten. Mögliche Ergebnisse:
   a) Anlage meldet state "partset" (oder ähnlich) -> Feature vorhanden.
      Exakten Zustandsstring notieren (auch in GET /system/partitions/
      prüfen, wie er dort erscheint).
   b) HTTP-Fehler oder state bleibt "unset" -> Feature nicht nutzbar,
      in CLAUDE.md dokumentieren, ARM_HOME NICHT freischalten, weiter
      mit Aufgabe 2.
3. Bei Erfolg: in alarm_control_panel.py ARM_HOME zu supported_features
   hinzufügen, async_alarm_arm_home implementieren, Zustandsmapping um
   den realen partset-String ergänzen (const.py).
4. Abnahme: Nutzer schaltet über die HA-Oberfläche Teilbereich 4 intern
   scharf und wieder unscharf; Zustand in HA stimmt mit Anlage überein.

## Aufgabe 2: Alarm-Erkennung (TRIGGERED)

Ziel: Ausgelöster Alarm wird in HA als "triggered" angezeigt —
Grundlage für alle Alarm-Automationen.

1. Recherche am Gerät (mit dem Nutzer koordinieren): Bei einem
   Testalarm auf Teilbereich 4 parallel die API pollen. Dafür ein
   Hilfsskript tools/watch_status.py schreiben, das /system/partitions/,
   /faults/ und /sec_global_status.cgx im 2-s-Takt abruft und jede
   Änderung mit Zeitstempel in watch_log.txt schreibt (nur lesend).
2. Nutzer bitten: Skript starten, Teilbereich 4 scharf schalten,
   Alarm auslösen (Anleitung mit dem Nutzer abstimmen — z.B. über die
   Anlage selbst), Alarm quittieren, Skript stoppen.
3. watch_log.txt auswerten: Wie sieht der Alarmzustand in welchem
   Endpoint aus? Exakte Strings in CLAUDE.md dokumentieren.
4. Implementieren: api.py/SecvestData um Alarmstatus erweitern,
   alarm_control_panel.py liefert AlarmControlPanelState.TRIGGERED.
   Auch den Zustand "Alarm quittiert aber nicht zurückgesetzt"
   berücksichtigen, falls die Anlage ihn unterscheidet.
5. Abnahme: zweiter Testalarm, HA zeigt "triggered", danach wieder
   Normalzustand.

## Aufgabe 3: Ereignisprotokoll (/logs/) als Sensor

Ziel: Sensor "Letztes Ereignis" mit Ereignistext, Zeitstempel und
auslösendem Benutzer.

1. Reale Payload holen: lesender Testaufruf GET /logs/ (ggf. mit
   ?limit=5, funktionierte laut Probe-Lauf). Struktur in CLAUDE.md
   dokumentieren (Feldnamen für Zeit, Text, Benutzer, Ereignistyp).
2. api.py: async_get_logs(limit) ergänzen; Logs in den Coordinator-
   Datenbestand aufnehmen (gleicher Poll-Zyklus, keine Extra-Requests
   außerhalb des Coordinators).
3. sensor.py neu anlegen: Sensor "Letztes Ereignis" (state = Kurztext,
   Attribute: Zeitstempel, Benutzer, Typ, die letzten 10 Ereignisse
   als Liste). Platform in __init__.py registrieren.
4. Abnahme: Nutzer schaltet an der Anlage, Sensor zeigt das Ereignis
   inkl. Benutzer innerhalb eines Poll-Intervalls.

## Aufgabe 4: Zonen als einzelne Binary Sensors

Ziel: Pro Melder eine eigene Entity (offen/geschlossen), nutzbar als
Fensterkontakt in anderen Automationen.

1. Vollständige Zonenliste finden: /system/partitions/ liefert nur
   Zonen-IDs (z.B. "301"). Kandidaten für Details lesend testen:
   /system/zones-301/, /zones-301/, /system/zone-301/. Falls nichts
   antwortet: Nutzer um DevTools-Mitschnitt der Zonen-/Melderseite
   der Web-UI bitten. Ergebnis in CLAUDE.md dokumentieren.
2. Implementieren: api.py um Zonenabfrage erweitern (Namen, Zustand,
   Zuordnung zum Teilbereich). Offene Zonen aus sec_global_status.cgx
   mit der Zonenliste zusammenführen.
3. binary_sensor.py: pro Zone eine Entity (device_class: opening bzw.
   motion, falls unterscheidbar), zusätzlich zu den bestehenden
   Störungssensoren. Stabile unique_ids (Zonen-ID, nicht Name).
4. Abnahme: Fenster/Tür öffnen -> Entity wechselt auf "offen".

## Aufgabe 5: Wartungs- und Batteriewarnungen

Ziel: Frühwarnung bei Batterie-/Funkproblemen.

1. /faults/-Payload systematisch auswerten: Felder type, is-rf-warning,
   prevents-set. Bekannte type-Codes in const.py als Mapping anlegen
   (5000 = offene Zone ist belegt; weitere Codes beim Auftreten
   dokumentieren, unbekannte Codes generisch anzeigen).
2. binary_sensor.py: einen anlagenweiten Sensor "Wartung" ergänzen
   (device_class: problem), der bei is-rf-warning oder Batterie-
   Störungen anspringt; Attribute mit Klartextmeldungen.
3. Optional (nach Rückfrage beim Nutzer): Beispiel-Automation als
   YAML-Snippet in README.md — Benachrichtigung bei Wartungsbedarf.
4. Abnahme: Sensor existiert, zeigt aktuell "aus" (keine Warnung) und
   listet bei vorhandenen Störungen die Meldungen.

## Aufgabe 6: Komfort & Qualität

Ziel: Integration alltagstauglich und wartbar machen.

1. Options Flow: Polling-Intervall (10-120 s) über die HA-UI
   einstellbar, Standard 15 s. Coordinator liest den Wert beim Setup.
2. Teilbereich-Auswahl: Im Config- und Options-Flow auswählbar machen,
   welche Teilbereiche als Entities angelegt werden. Standard: alle
   Teilbereiche mit mindestens einer Zone (leere wie "Teilber. 4"
   standardmäßig abgewählt, da nicht scharfschaltbar – 409). Abgewählte
   Teilbereiche erzeugen keine alarm_control_panel-Entity und werden
   nicht gepollt/bedient. Auswahl als Multi-Select über die HA-UI; beim
   Autor wird Teilbereich 4 nicht benötigt. Stabile unique_ids der
   verbleibenden Entities dürfen sich dabei NICHT ändern.
3. Reauth-Flow: Bei SecvestAuthError den HA-Reauth-Dialog auslösen,
   damit ein Passwortwechsel ohne Neuanlage der Integration möglich ist.
4. Tests: pytest + pytest-homeassistant-custom-component einrichten.
   Fixtures aus den in CLAUDE.md dokumentierten Payloads bauen (KEINE
   echten Zugangsdaten). Mindestens: Parser-Tests für partitions/faults/
   open_zones, Config-Flow-Test, ein Coordinator-Test mit Mock-Client.
5. Übersetzungen (de/en) für alle neuen Entities und den Options Flow
   vervollständigen; strings.json synchron halten.
6. HACS-Vorbereitung: hacs.json anlegen, README.md mit Installations-
   anleitung (manuell + HACS Custom Repo), Versionsnummer in
   manifest.json pflegen. Hinweis in README, dass die API inoffiziell
   und firmwareabhängig ist (verifiziert gegen die Firmware des Autors).
7. Abnahme: Testlauf pytest grün, Optionen in HA änderbar (inkl.
   Teilbereich-Auswahl), README vollständig.

---

## Nach Abschluss aller Aufgaben

- CLAUDE.md aufräumen: erledigte offene Punkte entfernen, API-Doku
  konsolidieren.
- Nutzer an Passwortwechsel der Anlage erinnern (stand im Chatverlauf
  und in einer HAR-Datei) und daran, die HAR-Datei zu löschen.
- Optional: GitHub-Repo + HACS-Veröffentlichung mit dem Nutzer besprechen.
