# Ferroli Electric for Home Assistant

Control Ferroli electric radiators (the ones managed by the **FERROLI ELECTRIC** app) from Home Assistant.

This is an unofficial integration. It talks to the same Ferroli cloud the app uses, so it needs internet access
and may break if Ferroli changes that API. It is not affiliated with or endorsed by Ferroli.

## Features

For every radiator on your account (all installations and zones):

- **Thermostat** (`climate`): on/off, target temperature, presets *Comfort*, *Eco*, *Anti-frost*, *Program*
  and *Boost* (forced mode at the current target for 1 hour, like the app's manual mode). Setting a temperature
  switches to Comfort at that value, as the app does.
- **Energy today** (kWh, works in the Energy dashboard) and **Cost today** (EUR), from the app's consumption graph.
- The app's **radiator configuration** settings, as configuration entities:

  | Entity | Range |
  | --- | --- |
  | Open window detection | on/off |
  | Adaptive start | on/off |
  | EASY mode | on/off |
  | Keypad lock | on/off |
  | Temperature offset | −5.0 … +5.0 °C, step 0.1 |
  | Power limit | 20 … 100 %, step 5 |
  | Display brightness | 0 / 30 / 60 / 90 % |
  | Display timeout | 1 … 240 s |

  Resetting or unpairing a radiator is deliberately not exposed.

### Unplugged radiators

The Ferroli cloud never marks an unplugged radiator as offline: it keeps serving its last state, so it would
look like it is still heating. This integration treats a radiator that hasn't reported for more than an hour
as offline: the thermostat shows **off** with no current temperature, and turning it on or changing a setting
fails with a clear error instead of queueing a change for whenever it gets plugged in again. Turning an
offline radiator off is accepted (it is off already). The thermostat's `online` and `last_report` attributes
show what the integration sees.

## Installation

### HACS

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/motanu8008/ha-ferroli-electric`, type **Integration**.
2. Install **Ferroli Electric** and restart Home Assistant.

### Manual

Copy `custom_components/ferroli_electric` into your Home Assistant `config/custom_components/` folder and restart.

## Configuration

Settings → Devices & services → **Add integration** → *Ferroli Electric*, then log in with the email and
password of your FERROLI ELECTRIC app account. Every radiator becomes a device named as in the app.

The cloud is polled every minute; energy and cost every 5 minutes. Changes are sent the same way the app sends them.

## Troubleshooting

- **Diagnostics**: the integration's ⋮ menu → *Download diagnostics* gives the raw radiator data as the cloud
  returns it (names and gateway ids are redacted). Attach it to an issue.
- **Debug logs**:

  ```yaml
  logger:
    logs:
      custom_components.ferroli_electric: debug
  ```

## License

[MIT](LICENSE)
