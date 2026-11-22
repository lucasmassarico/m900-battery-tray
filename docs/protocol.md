# Battery protocol: Delux M900 Pro on the 2.4 GHz receiver

This is what the app relies on to read the battery level. Everything below was verified on one
unit (Windows 11, 2.4 GHz receiver) unless it is marked otherwise.

## Receiver

| Item | Value |
|---|---|
| Product string | `2.4G 8K HS Receiver` |
| VID:PID | `1D57:FA65` |

The receiver exposes these HID collections (lengths include the report ID byte):

| Interface | Collection | Usage page : usage | Input / Output / Feature bytes | Role |
|---|---|---|---|---|
| MI_00 | | `0x0001:0x06` keyboard | 9 / 0 / 0 | keyboard (macros) |
| MI_01 | | `0x0001:0x02` mouse | 8 / 0 / 0 | pointer |
| MI_02 | COL01 | `0x0001:0x80` system control | 2 / 0 / 0 | |
| MI_02 | COL02 | `0x000C:0x01` consumer control | 3 / 0 / 0 | |
| MI_02 | **COL03** | **`0x000A:0x00`** | **5** / 0 / 0 | **battery reports** |
| MI_02 | COL04 | `0xFF00:0x01` vendor | 64 / 64 / 0 | vendor configuration channel |
| MI_03 | | `0x0001:0x06` keyboard | 15 / 0 / 0 | keyboard |

Windows locks the keyboard and mouse collections, but not COL03. Several programs can read COL03
at the same time, including the vendor app.

## Battery report

The receiver pushes a 5-byte input report on COL03 every 2.00 s. Nothing has to be sent to the
mouse to get it.

| Byte | Example | Meaning |
|---|---|---|
| 0 | `0x03` | report ID |
| 1 | `0x30` | model code. Other units report other values; do not filter on it |
| 2 | `0x40` | event: battery status. Other units send `0x41`; accept both |
| 3 | `0x01` | status: `1` = on battery, `3` = charging on the cable, `2` = full (not observed yet) |
| 4 | `0x4A` | **battery percentage** (74) |

```text
t=   1.81  03 30 40 01 4a    74 %, on battery
t=   3.82  03 30 40 01 4a
t=   1.11  03 30 40 03 4a    74 %, charging
t=   3.11  03 30 40 03 4a
```

With the `hidapi` package on Windows, `read()` returns the report ID as byte 0, matching the
table above.

## Parsing rules

- Accept a report only if it is 5 bytes long, byte 0 is `0x03`, byte 2 is `0x40` or `0x41`, and
  byte 4 is between 0 and 100.
- Show a new level only after two consecutive equal reports. The first report after a relink can
  be junk.
- Never write to the device. Reading the battery needs no output or feature report, and COL04
  belongs to the vendor app's configuration protocol.

## Observed behavior

- **Vendor app:** the percentage matches what the vendor app shows.
- **Mouse sleep:** with the vendor app's sleep time set to 1 min, the reports slowed from every
  2 s to every 4 s about 1 min after the mouse was last used, and stopped about 1 min after that.
  When the mouse moved again, reports came back every 2 s, and the first one was valid. So the
  receiver goes silent while the mouse sleeps, whatever the sleep time is.
- **Charging on the cable:** the mouse stays on the 2.4 GHz link. Reports keep coming every 2 s,
  byte 3 turns to `3` at once, and no other USB device shows up. **The percentage is not
  meaningful while charging:** it is re-read once, about 25 s after the cable goes in (78 %
  turned into 81 %), and then stays frozen until the cable comes out (81 % for a whole 46 min
  charge that actually filled the battery). A lone report with status `2` shows up every 5 to
  9 min during the charge, never twice in a row; the two-equal-reports rule ignores it.
- **Cable plugged in or unplugged:** right before the level is re-read, one report
  `03 30 40 01 64` (100 %, status 1) shows up. After a short charge it was junk: the level then
  settled within seconds (85, 84, 83 %) and dropped by 1 % every few minutes. After a full charge
  the level really was 100 %, and it stayed there.
- **Granularity:** the percentage moves in steps of 1.
- **PC sleep and resume:** the open handle keeps working. There is no read error and no device
  change, and reports resume on the same handle right after the PC wakes up.
- **Receiver unplugged:** the pending read fails at once and the collection leaves the device list
  about 0.4 s later. After the receiver is plugged back in, the collection comes back with the
  same path. Right after it is reopened, the receiver may flood about 200 junk reports
  (`03 00 c0 00 00`) within 50 ms; the event byte `0xC0` rejects them. Normal reports follow.

## Not verified yet

- **Status `2`:** what exactly it means. It only showed up as lone reports while charging.
- **Hibernation:** only a normal PC sleep was tested.
- **Bluetooth mode:** out of scope.
