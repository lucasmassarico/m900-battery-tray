"""Tray icon renderer: a mouse that fills from the bottom with the battery level.

The mouse is a hand-drawn pixel bitmap per layout size (16, 20, 24 and 32 px; sizes in between
use the next smaller one, centred), traced from the Segoe icon-font mouse (U+E962). No font is
loaded, so every pixel is exact and the icon looks the same on Windows 10 and 11. The exact
level is only in the tooltip; the icon shows it as a fill and a color band:

- on battery: 50 % and up in the taskbar's ink, 26-49 % with a soft amber fill, and 25 % or
  less the whole mouse turns red;
- charging: the whole mouse is green and the fill rises in a loop over CHARGING_FRAMES frames
  (the level is frozen while charging, so it isn't shown);
- asleep: dimmed, with a stippled fill of the last level, or a "z" without one;
- waiting for a level: dimmed, with three dots;
- receiver missing: dimmed, with a slash through the mouse.

The color bands are fixed, apart from the configurable alert thresholds: they are a scale to
read at a glance, and the alerts are the user's own triggers.
"""

from collections import deque
from dataclasses import dataclass
from enum import Enum
from functools import cache

from PIL import Image

from m900_battery_tray.state import DeviceState, Snapshot

RGB = tuple[int, int, int]
Bitmap = tuple[str, ...]
Point = tuple[int, int]


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
    caution: RGB
    critical: RGB
    charging: RGB
    dim_alpha: float


# Amber and red are tuned in OKLCH to the Fluent semantic colors, with softer chroma; each has
# at least 3:1 contrast against its taskbar. The light-theme red is darker than Fluent's so it
# stays apart from the amber under deuteranopia.
PALETTES = {
    TaskbarTheme.DARK: Palette(
        ink=(0xFF, 0xFF, 0xFF),
        caution=(0xEB, 0xBD, 0x57),
        critical=(0xF6, 0x6D, 0x67),
        charging=(0x6C, 0xCB, 0x5F),
        dim_alpha=0.55,
    ),
    TaskbarTheme.LIGHT: Palette(
        ink=(0x1A, 0x1A, 0x1A),
        caution=(0xA6, 0x77, 0x00),
        critical=(0xA5, 0x1F, 0x1B),
        charging=(0x0F, 0x7B, 0x0F),
        dim_alpha=0.70,
    ),
}

CAUTION_BELOW = 50
CRITICAL_AT_MOST = 25

# While charging the mouse reports a frozen level, so the fill rises in a loop instead
# (indeterminate progress), one step per frame. Frame 0 is the still icon, about half full.
CHARGING_FRAMES = 8

OUTLINE = "#"
WHEEL = "|"
EMPTY = "."

MOUSE_BITMAPS: dict[int, Bitmap] = {
    16: (
        "..#######..",
        ".#...|...#.",
        "#....|....#",
        "#....|....#",
        "#....|....#",
        "#....|....#",
        "#.........#",
        "#.........#",
        "#.........#",
        "#.........#",
        "#.........#",
        "#.........#",
        "#.........#",
        ".#.......#.",
        "..#.....#..",
        "...#####...",
    ),
    20: (
        "...#######...",
        ".##...|...##.",
        ".#....|....#.",
        "#.....|.....#",
        "#.....|.....#",
        "#.....|.....#",
        "#.....|.....#",
        "#...........#",
        "#...........#",
        "#...........#",
        "#...........#",
        "#...........#",
        "#...........#",
        "#...........#",
        "#...........#",
        "#...........#",
        ".#.........#.",
        ".#.........#.",
        "..##.....##..",
        "....#####....",
    ),
    24: (
        "...##########...",
        "..##...||...##..",
        ".##....||....##.",
        "##.....||.....##",
        "##.....||.....##",
        "##.....||.....##",
        "##.....||.....##",
        "##.....||.....##",
        "##............##",
        "##............##",
        "##............##",
        "##............##",
        "##............##",
        "##............##",
        "##............##",
        "##............##",
        "##............##",
        "##............##",
        "##............##",
        ".##..........##.",
        ".##..........##.",
        "..##........##..",
        "...###....###...",
        ".....######.....",
    ),
    32: (
        "....##############....",
        "...################...",
        "..###.....||.....###..",
        ".##.......||.......##.",
        "###.......||.......###",
        "##........||........##",
        "##........||........##",
        "##........||........##",
        "##........||........##",
        "##........||........##",
        "##........||........##",
        "##........||........##",
        "##..................##",
        "##..................##",
        "##..................##",
        "##..................##",
        "##..................##",
        "##..................##",
        "##..................##",
        "##..................##",
        "##..................##",
        "##..................##",
        "##..................##",
        "##..................##",
        ".##................##.",
        ".##................##.",
        ".###..............###.",
        "..###............###..",
        "...###..........###...",
        "....####......####....",
        ".....############.....",
        "........######........",
    ),
}
STROKES = {16: 1, 20: 1, 24: 2, 32: 2}
MIN_SIZE = min(MOUSE_BITMAPS)

Z_MARK: Bitmap = ("###", "..#", ".#.", "#..", "###")
DOT: Bitmap = ("#",)


def render_icon(
    snapshot: Snapshot, size: int, theme: TaskbarTheme, *, frame: int = 0
) -> Image.Image:
    """Draw the tray icon for a snapshot.

    `frame` only matters while charging: it picks one of CHARGING_FRAMES animation steps
    (wrapping around). Frame 0 works as a still icon on its own.
    """
    if size < MIN_SIZE:
        raise ValueError(f"icon size must be at least {MIN_SIZE} px, got {size}")
    mouse = _mouse(size)
    palette = PALETTES[theme]
    canvas = _Canvas(size)
    ink, dim = palette.ink, palette.dim_alpha
    state, percent = snapshot.state, snapshot.percent

    match state:
        case DeviceState.CONNECTED if percent is not None:
            fill_color = _band_color(percent, palette)
            outline_color = palette.critical if percent <= CRITICAL_AT_MOST else ink
            _fill(canvas, mouse, percent / 100, fill_color, 1.0)
            canvas.put_all(mouse.outline, outline_color, 1.0)
        case DeviceState.CHARGING:
            step = (frame + CHARGING_FRAMES // 2) % CHARGING_FRAMES
            _fill(canvas, mouse, step / (CHARGING_FRAMES - 1), palette.charging, 1.0)
            canvas.put_all(mouse.outline, palette.charging, 1.0)
        case DeviceState.ASLEEP if percent is not None:
            canvas.put_all(mouse.outline, ink, dim)
            _fill(canvas, mouse, percent / 100, ink, dim, stipple=True)
        case DeviceState.ASLEEP:
            canvas.put_all(mouse.outline, ink, dim)
            _draw_mark(canvas, mouse, Z_MARK, 0, ink, dim)
        case DeviceState.NO_RECEIVER:
            canvas.put_all(mouse.outline, ink, dim)
            _draw_slash(canvas, mouse, ink, dim)
        case _:
            canvas.put_all(mouse.outline, ink, dim)
            for index in (-1, 0, 1):
                _draw_mark(canvas, mouse, DOT, 2 * mouse.stroke * index, ink, dim)
    return canvas.image


def _band_color(percent: int, palette: Palette) -> RGB:
    if percent >= CAUTION_BELOW:
        return palette.ink
    return palette.critical if percent <= CRITICAL_AT_MOST else palette.caution


@dataclass(frozen=True)
class _Mouse:
    """The mouse bitmap placed on a canvas: outline pixels, the area the level fills (the
    interior minus a gap on each side of the wheel, so the wheel stays visible) and where the
    small marks go."""

    outline: frozenset[Point]
    fill_area: frozenset[Point]
    fill_top: int
    fill_bottom: int
    marks_top: int
    center_x: int
    stroke: int


@cache
def _mouse(size: int) -> _Mouse:
    layout = max(n for n in MOUSE_BITMAPS if n <= size)
    rows = MOUSE_BITMAPS[layout]
    width, height = len(rows[0]), len(rows)
    left, top = (size - width) // 2, (size - height) // 2
    cells = {(x, y): cell for y, row in enumerate(rows) for x, cell in enumerate(row)}
    outside = _reachable_from_the_border(cells, width, height)
    interior = {p for p, cell in cells.items() if cell == EMPTY and p not in outside}
    wheel = {p for p, cell in cells.items() if cell == WHEEL}
    beside_wheel = {(x + dx, y) for x, y in wheel for dx in (-1, 1)}
    interior_rows = [y for _, y in interior]

    def placed(points: set[Point]) -> frozenset[Point]:
        return frozenset((left + x, top + y) for x, y in points)

    return _Mouse(
        outline=placed({p for p, cell in cells.items() if cell != EMPTY}),
        fill_area=placed(interior - beside_wheel),
        fill_top=top + min(interior_rows),
        fill_bottom=top + max(interior_rows),
        marks_top=top + max(y for _, y in wheel) + 1,
        center_x=left + width // 2,
        stroke=STROKES[layout],
    )


def _reachable_from_the_border(cells: dict[Point, str], width: int, height: int) -> set[Point]:
    border = [
        (x, y)
        for (x, y), cell in cells.items()
        if cell == EMPTY and (x in (0, width - 1) or y in (0, height - 1))
    ]
    reached = set(border)
    queue = deque(border)
    while queue:
        x, y = queue.popleft()
        for neighbour in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if cells.get(neighbour) == EMPTY and neighbour not in reached:
                reached.add(neighbour)
                queue.append(neighbour)
    return reached


def _fill(
    canvas: "_Canvas",
    mouse: _Mouse,
    fraction: float,
    color: RGB,
    alpha: float,
    *,
    stipple: bool = False,
) -> None:
    rows = mouse.fill_bottom - mouse.fill_top + 1
    filled = max(round(rows * fraction), 1 if fraction > 0 else 0)
    first_row = mouse.fill_bottom - filled + 1
    canvas.put_all(
        {(x, y) for x, y in mouse.fill_area if y >= first_row and not (stipple and (x + y) % 2)},
        color,
        alpha,
    )


def _draw_mark(
    canvas: "_Canvas", mouse: _Mouse, mark: Bitmap, offset_x: int, color: RGB, alpha: float
) -> None:
    """Draw a small mark centred in the interior below the wheel, shifted by `offset_x`."""
    scale = mouse.stroke
    width, height = len(mark[0]) * scale, len(mark) * scale
    left = mouse.center_x - width // 2 + offset_x
    top = mouse.marks_top + (mouse.fill_bottom - mouse.marks_top + 1 - height) // 2
    canvas.put_all(
        {
            (left + column * scale + dx, top + row * scale + dy)
            for row, line in enumerate(mark)
            for column, cell in enumerate(line)
            if cell == OUTLINE
            for dy in range(scale)
            for dx in range(scale)
        },
        color,
        alpha,
    )


def _draw_slash(canvas: "_Canvas", mouse: _Mouse, color: RGB, alpha: float) -> None:
    """A diagonal from the bottom-left to the top-right, with a clear gap cut on each side."""
    size, stroke = canvas.size, mouse.stroke
    diagonal = size - 1
    for y in range(size):
        for x in range(size):
            distance = abs(x + y - diagonal)
            if distance <= stroke:
                canvas.erase((x, y))
            if distance < stroke and 0 < x < size - 1 and 0 < y < size - 1:
                canvas.put_all({(x, y)}, color, alpha)


class _Canvas:
    def __init__(self, size: int) -> None:
        self.size = size
        self.image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        self._pixels = self.image.load()

    def put_all(self, points: set[Point] | frozenset[Point], color: RGB, alpha: float) -> None:
        value = (*color, int(round(255 * alpha)))
        for point in points:
            self._pixels[point] = value

    def erase(self, point: Point) -> None:
        self._pixels[point] = (0, 0, 0, 0)
