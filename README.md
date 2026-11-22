# m900-battery-tray

A Windows 11 tray app that shows the battery level of the **Delux M900 Pro** wireless mouse
(2.4 GHz receiver `1D57:FA65`) and warns when it runs low, without the vendor software.

> Status: early development. Only the `--probe` diagnostic command works so far.

## How it works

The receiver pushes a 5-byte HID input report about every 2 seconds on a dedicated collection
(`MI_02` / `COL03`, usage page `0x000A`). Byte 4 of that report is the battery percentage.
The app only **reads** that collection: it never sends output or feature reports to the
receiver, and it never touches the vendor configuration channel (`COL04`).
See [docs/research.md](docs/research.md) for the protocol notes.

## Requirements

- Windows 10 or 11
- Python 3.12 or newer

## Development setup

```powershell
py -3.14 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
```

Checks:

```powershell
.venv\Scripts\ruff check .
.venv\Scripts\black --check .
.venv\Scripts\pytest
```

## Probe

`--probe` lists the receiver's HID collections and prints every raw battery frame with a
timestamp. It also logs when the receiver (`FA65`) or the wired-mode device (`FA60`) appears or
disappears. Use it to collect data for the open questions in the research notes.

```powershell
.venv\Scripts\python -m m900_battery_tray --probe --seconds 60
.venv\Scripts\python -m m900_battery_tray --probe --out captures\sleep.txt
```

Without `--seconds` the probe runs until Ctrl+C. `--out` appends the same output to a file.

Sample output:

```text
# 2026-11-22T14:02:01.390  t=    0.00  7 collection(s) found
# 1D57:FA65  MI_02  usage 0x000a:0x00  '2.4G 8K HS Receiver'  \\?\hid#vid_1d57&pid_fa65&mi_02&col03#...
# 2026-11-22T14:02:01.412  t=    0.02  opened battery collection \\?\hid#vid_1d57&pid_fa65&mi_02&col03#...
2026-11-22T14:02:03.130  t=    1.74  dt=     -  03 30 40 01 4c
2026-11-22T14:02:05.130  t=    3.74  dt=  2.00  03 30 40 01 4c
```

Lines that start with `#` are events; the others are frames (`03 <model> <event> <state> <percent>`).
