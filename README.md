# M900 Battery Tray

Shows the battery level of your **Delux M900 Pro** wireless mouse in the Windows tray and warns
you when it runs low. You don't need the Delux software.

> **Status:** it works when run from source. A ready-to-run `.exe` is coming.

## What it does

- Shows the battery percentage as the tray icon, with a small battery gauge under it.
- Shows the model, percentage and state in the tooltip and at the top of the right-click menu.
- Sends a Windows notification when the battery drops to 20 %, and again at 10 %.
- Starts with Windows, if you tick **Start with Windows** in the right-click menu.

It works with the mouse's 2.4 GHz receiver (`1D57:FA65`). Bluetooth is not supported.

### Reading the icon

| Icon | Meaning |
|---|---|
| White (or black on a light taskbar) number and gauge | On battery |
| Amber | Low battery (20 % or less) |
| Red | Critical battery (10 % or less) |
| Green lightning bolt, with a block moving through the gauge | Charging. The mouse doesn't report its real level while the cable is in, so the number comes back after you unplug it. The block stays still if Windows animation effects are off |
| Faded, dotted gauge | The mouse is asleep. The number is the last known level |
| Faded, three dots in the gauge | Waiting for the first reading |
| Faded, with an ✕ | The USB receiver is unplugged |

The icon follows the light or dark taskbar theme. Windows 11 hides new tray icons at first: to
keep it visible, open **Settings > Personalization > Taskbar > Other system tray icons** and turn
it on.

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

Start it without a console window:

```powershell
.venv\Scripts\pythonw -m m900_battery_tray
```

Only one copy runs at a time. To quit, right-click the icon and choose **Exit**. If something
goes wrong, the log is in `%APPDATA%\m900-battery-tray\app.log`.

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
