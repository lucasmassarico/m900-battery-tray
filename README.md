# M900 Battery Tray

Shows the battery level of your **Delux M900 Pro** wireless mouse in the Windows tray and warns
you when it runs low. You don't need the Delux software.

## What it does

- Shows the battery level as a mouse icon in the tray that fills up and changes color.
- Shows the model, percentage and state in the tooltip and at the top of the right-click menu.
- Sends a Windows notification when the battery drops to 20 %, and again at 10 %.
- Starts with Windows, if you tick **Start with Windows** in the right-click menu.
- Opens its settings file from the right-click menu (**Edit settings**) and applies changes when
  you save it, without a restart.

It works with the mouse's 2.4 GHz receiver (`1D57:FA65`). Bluetooth is not supported.

### Reading the icon

| Icon | Meaning |
|---|---|
| White (or black on a light taskbar) mouse | On battery, 50 % or more. The fill shows the level |
| Amber fill | 26 to 49 % |
| Red mouse | 25 % or less |
| Green mouse, filling up over and over | Charging. The mouse doesn't report its real level while the cable is in, so the level comes back after you unplug it. The fill stays still if Windows animation effects are off |
| Faded, dotted fill | The mouse is asleep. The fill is the last known level |
| Faded, with a "z" | The mouse is asleep and no level has been read yet |
| Faded, three dots | Waiting for the first reading |
| Faded, crossed out | The USB receiver is unplugged |

Hover over the icon for the exact percentage.

The icon and its right-click menu follow the light or dark taskbar theme. Windows 11 hides new tray icons at first: to
keep it visible, open **Settings > Personalization > Taskbar > Other system tray icons** and turn
it on.

## Is it safe?

The app only **reads** the battery reports that the receiver already sends every 2 seconds. It
never sends anything to the mouse or the receiver, so it can't change your mouse settings. It runs
fine alongside the Delux software.

## Install

You need Windows 10 or 11.

1. Download `m900-battery-tray-<version>-win64.zip` from the
   [latest release](https://github.com/lucasmassarico/m900-battery-tray/releases/latest).
2. Extract the `m900-battery-tray` folder to a place where it can stay, for example
   `%LOCALAPPDATA%\Programs`.
3. Run `m900-battery-tray.exe` in that folder. The exe isn't signed, so Windows SmartScreen may
   warn the first time (**More info > Run anyway**).

Only one copy runs at a time. To quit, right-click the icon and choose **Exit**. If something
goes wrong, the log is in `%APPDATA%\m900-battery-tray\app.log`.

If you move the folder later, start the app once from its new place: **Start with Windows**
follows it.

## Run from source

You need [Python](https://www.python.org/downloads/) 3.12 or newer.

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

To change them, right-click the icon and choose **Edit settings**. The file opens in your default
app for `.json` files, or in Notepad if there is none. The app applies your changes as soon as
you save the file, and confirms with a notification. If the file has a mistake, the notification
says what is wrong and the app keeps the previous settings.

| Setting | Meaning | Allowed values |
|---|---|---|
| `low_battery_percent` | First warning | 2 to 99, above `critical_battery_percent` |
| `critical_battery_percent` | Second warning | 1 to 98 |
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

With the packaged app, run the probe from PowerShell in the app's folder. The `| Out-Host` makes
PowerShell wait for the probe to finish before it shows the prompt again:

```powershell
.\m900-battery-tray.exe --probe --seconds 30 | Out-Host
```

## Development

```powershell
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\ruff check .
.venv\Scripts\black --check .
.venv\Scripts\pytest
```

To build the packaged app (a folder with `m900-battery-tray.exe`, no Python needed to run it):

```powershell
.venv\Scripts\python -m pip install -e ".[build]"
.venv\Scripts\python scripts\build_exe.py
```

The folder is `dist\m900-battery-tray\`, and `dist\m900-battery-tray-<version>-win64.zip` holds the
same folder, ready to share. The exe isn't signed, so Windows SmartScreen may warn the first time it
runs (**More info > Run anyway**).

The battery protocol is described in [docs/protocol.md](docs/protocol.md).
