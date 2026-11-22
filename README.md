# M900 Battery Tray

Shows the battery level of your **Delux M900 Pro** wireless mouse in the Windows tray and warns
you when it runs low. You don't need the Delux software.

> **Work in progress.** The tray app is not ready yet. For now you can run the diagnostic probe
> described below.

## What it will do

- Show the battery percentage as the tray icon, colored by level: normal, low or critical.
- Show the model, percentage and state (connected, charging, asleep, receiver missing) in the
  tooltip.
- Send a Windows notification when the battery drops below 20 % and again below 10 %.
- Start with Windows, if you turn it on from the tray menu.

It works with the mouse's 2.4 GHz receiver (`1D57:FA65`). Bluetooth is not supported.

## Is it safe?

The app only **reads** the battery reports that the receiver already sends every 2 seconds. It
never sends anything to the mouse or the receiver, so it can't change your mouse settings. It runs
fine alongside the Delux software.

## Install (from source)

You need Windows 10 or 11 and [Python](https://www.python.org/downloads/) 3.12 or newer.

```powershell
git clone https://github.com/lucasmassarico/m900-battery-tray.git
cd m900-battery-tray
py -m venv .venv
.venv\Scripts\python -m pip install -e .
```

## Settings

The app keeps its settings in `%APPDATA%\m900-battery-tray\config.json`. It creates the file with
these defaults the first time it runs:

```json
{
  "version": 1,
  "low_battery_percent": 20,
  "critical_battery_percent": 10,
  "sleep_after_seconds": 15
}
```

| Setting | Meaning | Allowed values |
|---|---|---|
| `low_battery_percent` | First warning, and the start of the "low" icon color | 2 to 99, above `critical_battery_percent` |
| `critical_battery_percent` | Second warning, and the start of the "critical" icon color | 1 to 98 |
| `sleep_after_seconds` | Seconds without battery reports before the mouse is shown as asleep | 12 to 3600 |

`sleep_after_seconds` is not the mouse's own sleep time (the one you set in the Delux app). The
receiver goes quiet when the mouse sleeps, whatever that setting is, and this value only says how
long the app waits for that silence before it shows "asleep".

## Probe (diagnostics)

The probe lists the receiver's HID collections and prints every battery report it receives with a
timestamp. Use it if the app can't find your mouse, or to check what your receiver sends.

```powershell
.venv\Scripts\python -m m900_battery_tray --probe --seconds 30
```

```text
# 2026-11-22T14:01:30.440  t=    0.11  opened battery collection \\?\HID#VID_1D57&PID_FA65&MI_02&Col03#...
2026-11-22T14:01:32.137  t=    1.81  dt=     -  03 30 40 01 4a
2026-11-22T14:01:34.147  t=    3.82  dt=  2.01  03 30 40 01 4a
```

The last byte is the battery percentage (`4a` = 74 %). Without `--seconds` the probe runs until
you press Ctrl+C, and `--out file.txt` also saves the output to a file.

## Development

```powershell
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\ruff check .
.venv\Scripts\black --check .
.venv\Scripts\pytest
```

The battery protocol is described in [docs/protocol.md](docs/protocol.md).
