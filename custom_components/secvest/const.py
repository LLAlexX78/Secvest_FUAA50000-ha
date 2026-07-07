"""Konstanten für die ABUS Secvest Integration.

Endpoints verifiziert am 07.07.2026 per HAR-Mitschnitt und Probe-Skript
gegen eine Secvest FUAA50000 (Web-UI mit sec_*.cgi/.cgx-Struktur):

  GET /system/partitions/          -> JSON-Array aller Teilbereiche
  PUT /system/partitions-{n}/      -> {"state": "set"|"unset"} schaltet
  GET /faults/                     -> JSON-Array Störungen (prevents-set!)
  GET /sec_global_status.cgx       -> XML-artig, enthält offene Zonen
  GET /logs/                       -> JSON Ereignisprotokoll

Auth: HTTP Basic (Benutzer Code + Web-Passwort). Fallback: Form-Login
POST /sec_login.cgi mit usr=<code>&pwd=<passwort> (Session-Cookie).
"""

DOMAIN = "secvest"

CONF_VERIFY_SSL = "verify_ssl"

DEFAULT_PORT = 4433
DEFAULT_SCAN_INTERVAL = 15  # Sekunden; Web-UI selbst pollt ~2 s
DEFAULT_VERIFY_SSL = False  # selbstsigniertes Zertifikat

ENDPOINT_PARTITIONS = "/system/partitions/"
ENDPOINT_PARTITION_SET = "/system/partitions-{p}/"
ENDPOINT_FAULTS = "/faults/"
ENDPOINT_GLOBAL_STATUS = "/sec_global_status.cgx"
ENDPOINT_LOGS = "/logs/"
ENDPOINT_FORM_LOGIN = "/sec_login.cgi"

# Zustände laut API: "set" | "unset" (verifiziert).
# "partset" (intern scharf) ist plausibel, aber noch NICHT verifiziert.
STATE_SET = "set"
STATE_UNSET = "unset"
STATE_PARTSET = "partset"
