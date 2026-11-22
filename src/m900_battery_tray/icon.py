"""Tray icon renderer: the battery number in a pixel font over a small battery gauge.

Drawn pixel-exact at the tray's small-icon size (16, 20, 24 or 32 px), on a transparent
background, in colors that work on the light or the dark taskbar. Each state differs by shape,
not only by color:

- on battery: solid gauge; low and critical levels turn digits, fill and outline amber or red;
- charging: a green bolt in place of the number (the level is frozen while charging) and a
  green block travelling through the gauge, over CHARGING_FRAMES animation frames;
- asleep: dimmed, with a stippled fill of the last level;
- waiting for a level: dimmed, with three dots in the gauge;
- receiver missing: dimmed, with a cross in place of the gauge.
"""

from dataclasses import dataclass
from enum import Enum

from PIL import Image

from m900_battery_tray.state import DeviceState, Snapshot

RGB = tuple[int, int, int]
Bitmap = tuple[str, ...]


class TaskbarTheme(Enum):
    DARK = "dark"
    LIGHT = "light"

    @classmethod
    def from_system_uses_light_theme(cls, value: object) -> "TaskbarTheme":
        """Map the registry value SystemUsesLightTheme; Windows 11 defaults to dark."""
        return cls.LIGHT if value == 1 else cls.DARK


@dataclass(frozen=True)
class Palette:
    ink: RGB
    low: RGB
    critical: RGB
    charging: RGB
    dim_alpha: float


PALETTES = {
    TaskbarTheme.DARK: Palette(
        ink=(0xFF, 0xFF, 0xFF),
        low=(0xFC, 0xE1, 0x00),
        critical=(0xFF, 0x99, 0xA4),
        charging=(0x6C, 0xCB, 0x5F),
        dim_alpha=0.55,
    ),
    TaskbarTheme.LIGHT: Palette(
        ink=(0x1A, 0x1A, 0x1A),
        low=(0x9D, 0x5D, 0x00),
        critical=(0xC4, 0x2B, 0x1C),
        charging=(0x0F, 0x7B, 0x0F),
        dim_alpha=0.70,
    ),
}

OUTLINE_ALPHA = 0.75
BAND_OUTLINE_ALPHA = 0.85

FONT_4X7: dict[str, Bitmap] = {
    "0": (".##.", "#..#", "#..#", "#..#", "#..#", "#..#", ".##."),
    "1": ("..#.", ".##.", "..#.", "..#.", "..#.", "..#.", ".###"),
    "2": (".##.", "#..#", "...#", "..#.", ".#..", "#...", "####"),
    "3": (".##.", "#..#", "...#", "..#.", "...#", "#..#", ".##."),
    "4": ("...#", "..##", ".#.#", "#..#", "####", "...#", "...#"),
    "5": ("####", "#...", "###.", "...#", "...#", "#..#", ".##."),
    "6": (".##.", "#...", "#...", "###.", "#..#", "#..#", ".##."),
    "7": ("####", "...#", "..#.", "..#.", ".#..", ".#..", ".#.."),
    "8": (".##.", "#..#", "#..#", ".##.", "#..#", "#..#", ".##."),
    "9": (".##.", "#..#", "#..#", ".###", "...#", "...#", ".##."),
    "-": ("....", "....", "....", "####", "....", "....", "...."),
}
FONT_3X5: dict[str, Bitmap] = {
    "0": ("###", "#.#", "#.#", "#.#", "###"),
    "1": (".#.", "##.", ".#.", ".#.", "###"),
    "2": ("###", "..#", "###", "#..", "###"),
    "3": ("###", "..#", "###", "..#", "###"),
    "4": ("#.#", "#.#", "###", "..#", "..#"),
    "5": ("###", "#..", "###", "..#", "###"),
    "6": ("###", "#..", "###", "#.#", "###"),
    "7": ("###", "..#", "..#", "..#", "..#"),
    "8": ("###", "#.#", "###", "#.#", "###"),
    "9": ("###", "#.#", "###", "..#", "###"),
    "-": ("...", "...", "###", "...", "..."),
}
BOLT: Bitmap = ("..##", ".##.", ".###", "..#.", ".#..")
BOLT_7: Bitmap = ("...##", "..##.", ".##..", ".####", "..##.", ".##..", "##...")
CROSS: Bitmap = ("#...#", ".#.#.", "..#..", ".#.#.", "#...#")

# While charging the mouse reports a frozen level, so the icon shows a bolt instead of a number
# and a block travelling through the gauge (indeterminate progress), one step per frame.
CHARGING_FRAMES = 8


@dataclass(frozen=True)
class _Layout:
    font: dict[str, Bitmap]
    digit_scale: int
    digit_gap: int
    digit_y: int
    gauge_y: int
    gauge_height: int
    stroke: int
    bolt: Bitmap
    bolt_scale: int


_LAYOUTS = {
    16: _Layout(
        FONT_4X7,
        digit_scale=1,
        digit_gap=1,
        digit_y=1,
        gauge_y=10,
        gauge_height=5,
        stroke=1,
        bolt=BOLT_7,
        bolt_scale=1,
    ),
    20: _Layout(
        FONT_4X7,
        digit_scale=1,
        digit_gap=1,
        digit_y=2,
        gauge_y=12,
        gauge_height=6,
        stroke=1,
        bolt=BOLT_7,
        bolt_scale=1,
    ),
    24: _Layout(
        FONT_3X5,
        digit_scale=2,
        digit_gap=2,
        digit_y=2,
        gauge_y=15,
        gauge_height=7,
        stroke=1,
        bolt=BOLT,
        bolt_scale=2,
    ),
    32: _Layout(
        FONT_4X7,
        digit_scale=2,
        digit_gap=2,
        digit_y=3,
        gauge_y=19,
        gauge_height=10,
        stroke=2,
        bolt=BOLT_7,
        bolt_scale=2,
    ),
}
MIN_SIZE = min(_LAYOUTS)


def render_icon(
    snapshot: Snapshot,
    size: int,
    theme: TaskbarTheme,
    *,
    low_percent: int,
    critical_percent: int,
    frame: int = 0,
) -> Image.Image:
    """Draw the tray icon for a snapshot. Sizes between layouts use the next smaller one.

    `frame` only matters while charging: it picks one of CHARGING_FRAMES animation steps
    (wrapping around). Frame 0 works as a still icon on its own.
    """
    if size < MIN_SIZE:
        raise ValueError(f"icon size must be at least {MIN_SIZE} px, got {size}")
    layout = _LAYOUTS[max(n for n in _LAYOUTS if n <= size)]
    palette = PALETTES[theme]
    canvas = _Canvas(size)
    state, percent = snapshot.state, snapshot.percent
    text = "--" if percent is None else str(percent)

    if state is DeviceState.CHARGING:
        _draw_charging(canvas, layout, palette, frame % CHARGING_FRAMES)
    elif state is DeviceState.CONNECTED:
        color = _band_color(percent, palette, low_percent, critical_percent)
        canvas.text(text, layout, color, 1.0)
        outline_alpha = OUTLINE_ALPHA if color == palette.ink else BAND_OUTLINE_ALPHA
        _draw_battery(canvas, layout, color, outline_alpha)
        canvas.gauge_fill(layout, size - layout.stroke, percent, color, 1.0, stipple=False)
    else:
        dim = palette.dim_alpha
        canvas.text(text, layout, palette.ink, dim)
        if state is DeviceState.NO_RECEIVER:
            _draw_cross(canvas, layout, palette.ink, dim)
        else:
            _draw_battery(canvas, layout, palette.ink, OUTLINE_ALPHA * dim)
            if state is DeviceState.ASLEEP:
                width = size - layout.stroke
                canvas.gauge_fill(layout, width, percent, palette.ink, dim, stipple=True)
            else:
                _draw_waiting_dots(canvas, layout, palette.ink, dim)
    return canvas.image


def _band_color(percent: int | None, palette: Palette, low: int, critical: int) -> RGB:
    if percent is None or percent > low:
        return palette.ink
    return palette.critical if percent <= critical else palette.low


def _draw_battery(canvas: "_Canvas", layout: _Layout, color: RGB, alpha: float) -> None:
    stroke, top, height = layout.stroke, layout.gauge_y, layout.gauge_height
    width = canvas.size - stroke
    canvas.outline(0, top, width, height, stroke, color, alpha)
    nub_height = height - 4 * stroke if height > 4 * stroke else stroke
    nub_top = top + (height - nub_height) // 2
    canvas.rect(width, nub_top, width + stroke - 1, nub_top + nub_height - 1, color, alpha)


def _draw_charging(canvas: "_Canvas", layout: _Layout, palette: Palette, frame: int) -> None:
    bolt_width = len(layout.bolt[0]) * layout.bolt_scale
    bolt_left = canvas.size // 2 - bolt_width // 2
    canvas.bitmap(layout.bolt, bolt_left, layout.digit_y, palette.charging, 1.0, layout.bolt_scale)
    _draw_battery(canvas, layout, palette.ink, OUTLINE_ALPHA)

    stroke = layout.stroke
    inside_width = canvas.size - 3 * stroke
    inside_top = layout.gauge_y + stroke
    inside_height = layout.gauge_height - 2 * stroke
    block_width = max(3, round(inside_width / 3))
    start = (inside_width - block_width) // 2 + round(frame * inside_width / CHARGING_FRAMES)
    for offset in range(block_width):
        x = stroke + (start + offset) % inside_width
        canvas.rect(x, inside_top, x, inside_top + inside_height - 1, palette.charging, 1.0)


def _draw_waiting_dots(canvas: "_Canvas", layout: _Layout, color: RGB, alpha: float) -> None:
    stroke = layout.stroke
    middle = layout.gauge_y + layout.gauge_height // 2
    top = middle - stroke // 2 if stroke > 1 else middle
    for index in range(3):
        left = 3 * stroke + 4 * stroke * index
        canvas.rect(left, top, left + stroke - 1, top + stroke - 1, color, alpha)


def _draw_cross(canvas: "_Canvas", layout: _Layout, color: RGB, alpha: float) -> None:
    scale = layout.stroke
    side = 5 * scale
    top = layout.gauge_y + (layout.gauge_height - side) // 2
    canvas.bitmap(CROSS, (canvas.size - side) // 2, top, color, alpha, scale)


class _Canvas:
    def __init__(self, size: int) -> None:
        self.size = size
        self.image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        self._pixels = self.image.load()

    def put(self, x: int, y: int, color: RGB, alpha: float) -> None:
        self._pixels[x, y] = (*color, int(round(255 * alpha)))

    def rect(self, x0: int, y0: int, x1: int, y1: int, color: RGB, alpha: float) -> None:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.put(x, y, color, alpha)

    def outline(
        self, x: int, y: int, width: int, height: int, stroke: int, color: RGB, alpha: float
    ) -> None:
        right, bottom = x + width - 1, y + height - 1
        self.rect(x, y, right, y + stroke - 1, color, alpha)
        self.rect(x, bottom - stroke + 1, right, bottom, color, alpha)
        self.rect(x, y, x + stroke - 1, bottom, color, alpha)
        self.rect(right - stroke + 1, y, right, bottom, color, alpha)

    def bitmap(
        self, rows: Bitmap, x: int, y: int, color: RGB, alpha: float, scale: int = 1
    ) -> None:
        for row_index, row in enumerate(rows):
            for column, cell in enumerate(row):
                if cell == "#":
                    left, top = x + column * scale, y + row_index * scale
                    self.rect(left, top, left + scale - 1, top + scale - 1, color, alpha)

    def text(self, text: str, layout: _Layout, color: RGB, alpha: float) -> None:
        glyphs = [layout.font[char] for char in text]
        scale, gap = layout.digit_scale, layout.digit_gap
        width = sum(len(glyph[0]) for glyph in glyphs) * scale + (len(glyphs) - 1) * gap
        x = self.size // 2 - width // 2
        for glyph in glyphs:
            self.bitmap(glyph, x, layout.digit_y, color, alpha, scale)
            x += len(glyph[0]) * scale + gap

    def gauge_fill(
        self,
        layout: _Layout,
        width: int,
        percent: int | None,
        color: RGB,
        alpha: float,
        *,
        stipple: bool,
    ) -> None:
        if percent is None:
            return
        stroke = layout.stroke
        inside_width = width - 2 * stroke
        inside_height = layout.gauge_height - 2 * stroke
        filled = min(inside_width, max(round(inside_width * percent / 100), 1 if percent else 0))
        for row in range(inside_height):
            for column in range(filled):
                if stipple and (column + row) % 2:
                    continue
                self.put(stroke + column, layout.gauge_y + stroke + row, color, alpha)
