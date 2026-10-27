"""Constants for the Ferroli Electric integration."""

DOMAIN = "ferroli_electric"
API_URL = "https://gateway.grupoferroli.es/APIGW"
CLIENT_ID = "AppFerroli"
# Poll every minute while a radiator is on, every 5 minutes while all are off (nothing changes then; switching
# one on from the radiator or the app shows up within that time, from HA right away).
SCAN_INTERVAL_ON = 60
SCAN_INTERVAL_OFF = 300
# Used when the radiator doesn't report its own anti-frost setpoint.
DEFAULT_ANTIFROST_TEMP = 7.0

# IdModoActual values used by the Ferroli app.
MODE_COMFORT = "C"
MODE_ECO = "E"
MODE_ANTIFROST = "A"
MODE_PROGRAM = "P"
MODE_FORCED = "M"

PRESET_TO_MODE = {
    "comfort": MODE_COMFORT,
    "eco": MODE_ECO,
    "away": MODE_ANTIFROST,
    "program": MODE_PROGRAM,
}
MODE_TO_PRESET = {v: k for k, v in PRESET_TO_MODE.items()} | {MODE_FORCED: "boost"}
