"""Render every tray icon state on light and dark taskbar backgrounds into one PNG.

Usage: python scripts/preview_icons.py [output.png]   (default: build/icon-preview.png)

Each cell shows the icon at real size in the top-left corner and an 8x nearest-neighbour
enlargement under it, so the pixel grid can be checked.
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

from m900_battery_tray.icon import TaskbarTheme, render_icon
from m900_battery_tray.state import DeviceState, Snapshot

SIZES = (16, 20, 24, 32)
ZOOM = 8
BACKGROUNDS = {TaskbarTheme.DARK: (0x20, 0x20, 0x20), TaskbarTheme.LIGHT: (0xF3, 0xF3, 0xF3)}
SAMPLES = (  # label, state, percent, animation frame
    ("on battery 85", DeviceState.CONNECTED, 85, 0),
    ("on battery 100", DeviceState.CONNECTED, 100, 0),
    ("low 18", DeviceState.CONNECTED, 18, 0),
    ("critical 7", DeviceState.CONNECTED, 7, 0),
    *((f"charging, frame {frame}", DeviceState.CHARGING, None, frame) for frame in range(8)),
    ("asleep 42", DeviceState.ASLEEP, 42, 0),
    ("asleep, no level", DeviceState.ASLEEP, None, 0),
    ("waiting 42", DeviceState.WAITING, 42, 0),
    ("waiting, no level", DeviceState.WAITING, None, 0),
    ("no receiver 63", DeviceState.NO_RECEIVER, 63, 0),
    ("no receiver, no level", DeviceState.NO_RECEIVER, None, 0),
)
LABEL_WIDTH = 140
HEADER_HEIGHT = 18
PADDING = 6
CELL = max(SIZES) * ZOOM + max(SIZES) + 3 * PADDING


def main(output: Path) -> None:
    columns = [(theme, size) for theme in BACKGROUNDS for size in SIZES]
    sheet = Image.new(
        "RGB",
        (LABEL_WIDTH + len(columns) * CELL, HEADER_HEIGHT + len(SAMPLES) * CELL),
        (0x80, 0x80, 0x80),
    )
    draw = ImageDraw.Draw(sheet)
    for column, (theme, size) in enumerate(columns):
        draw.text((LABEL_WIDTH + column * CELL + PADDING, 3), f"{theme.value} {size}px", "white")
    for row, (label, state, percent, frame) in enumerate(SAMPLES):
        top = HEADER_HEIGHT + row * CELL
        draw.text((PADDING, top + CELL // 2), label, "white")
        for column, (theme, size) in enumerate(columns):
            left = LABEL_WIDTH + column * CELL
            draw.rectangle((left + 1, top + 1, left + CELL - 1, top + CELL - 1), BACKGROUNDS[theme])
            icon = render_icon(
                Snapshot(state=state, percent=percent),
                size,
                theme,
                low_percent=20,
                critical_percent=10,
                frame=frame,
            )
            sheet.paste(icon, (left + PADDING, top + PADDING), icon)
            zoomed = icon.resize((size * ZOOM, size * ZOOM), Image.Resampling.NEAREST)
            sheet.paste(zoomed, (left + PADDING, top + 2 * PADDING + size), zoomed)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    print(output)


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("build/icon-preview.png"))
