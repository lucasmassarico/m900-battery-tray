import pytest
from PIL import Image

from m900_battery_tray.icon import CHARGING_FRAMES, PALETTES, TaskbarTheme, render_icon
from m900_battery_tray.state import DeviceState, Snapshot

DARK = TaskbarTheme.DARK
LIGHT = TaskbarTheme.LIGHT
DARK_PALETTE = PALETTES[DARK]
LIGHT_PALETTE = PALETTES[LIGHT]

# The 16 px mouse: 11 px wide in columns 2-12, scroll wheel in column 7 on rows 1-5.
MOUSE_16 = (
    "....#######.....",
    "...#...#...#....",
    "..#....#....#...",
    "..#....#....#...",
    "..#....#....#...",
    "..#....#....#...",
    "..#.........#...",
    "..#.........#...",
    "..#.........#...",
    "..#.........#...",
    "..#.........#...",
    "..#.........#...",
    "..#.........#...",
    "...#.......#....",
    "....#.....#.....",
    ".....#####......",
)
INSIDE_16 = frozenset(
    (x, y)
    for y, row in enumerate(MOUSE_16)
    if row.count("#") > 1
    for x in range(row.index("#") + 1, row.rindex("#"))
    if row[x] == "."
)
OUTLINE_PIXEL = (2, 6)
BOTTOM_FILL_PIXEL = (7, 14)


def render(
    state: DeviceState,
    percent: int | None,
    size: int = 16,
    theme: TaskbarTheme = DARK,
    frame: int = 0,
) -> Image.Image:
    return render_icon(Snapshot(state=state, percent=percent), size, theme, frame=frame)


def opaque_mask(image: Image.Image) -> list[str]:
    return [
        "".join("#" if image.getpixel((x, y))[3] else "." for x in range(image.width))
        for y in range(image.height)
    ]


def opaque_inside(image: Image.Image) -> set[tuple[int, int]]:
    return {point for point in INSIDE_16 if image.getpixel(point)[3]}


def filled_rows(image: Image.Image) -> int:
    return len({y for _, y in opaque_inside(image)})


def alpha(level: float) -> int:
    return int(round(255 * level))


@pytest.mark.parametrize(("value", "theme"), [(1, LIGHT), (0, DARK), (None, DARK), ("1", DARK)])
def test_taskbar_theme_from_the_registry_value(value: object, theme: TaskbarTheme) -> None:
    assert TaskbarTheme.from_system_uses_light_theme(value) is theme


@pytest.mark.parametrize("size", range(16, 41))
@pytest.mark.parametrize("state", list(DeviceState))
@pytest.mark.parametrize("percent", [None, 0, 7, 100])
def test_every_state_is_a_transparent_square_of_any_size(
    size: int, state: DeviceState, percent: int | None
) -> None:
    image = render(state, percent, size=size)

    assert image.mode == "RGBA"
    assert image.size == (size, size)
    assert image.getpixel((0, 0))[3] == 0
    assert image.getbbox() is not None


@pytest.mark.parametrize("size", range(16, 41))
@pytest.mark.parametrize("frame", range(CHARGING_FRAMES))
def test_every_charging_frame_fits_every_size(size: int, frame: int) -> None:
    assert render(DeviceState.CHARGING, None, size=size, frame=frame).size == (size, size)


def test_sizes_below_16_are_rejected() -> None:
    with pytest.raises(ValueError, match="at least 16"):
        render(DeviceState.CONNECTED, 85, size=15)


def test_the_16_px_mouse_is_pixel_exact() -> None:
    assert opaque_mask(render(DeviceState.CONNECTED, 0)) == list(MOUSE_16)


@pytest.mark.parametrize(
    ("state", "percent", "frame"),
    [
        (DeviceState.CONNECTED, 85, 0),
        (DeviceState.CONNECTED, 30, 0),
        (DeviceState.CHARGING, None, 3),
    ],
)
def test_sizes_between_layouts_centre_the_smaller_layout(
    state: DeviceState, percent: int | None, frame: int
) -> None:
    larger = render(state, percent, size=18, frame=frame)

    assert larger.crop((1, 1, 17, 17)).tobytes() == render(state, percent, frame=frame).tobytes()


@pytest.mark.parametrize(
    ("percent", "rows"), [(100, 14), (75, 10), (50, 7), (25, 4), (10, 1), (1, 1), (0, 0)]
)
def test_the_fill_rises_with_the_level(percent: int, rows: int) -> None:
    assert filled_rows(render(DeviceState.CONNECTED, percent)) == rows


def test_the_wheel_stays_visible_in_a_full_mouse() -> None:
    image = render(DeviceState.CONNECTED, 100)

    for y in range(1, 6):
        assert image.getpixel((6, y))[3] == 0
        assert image.getpixel((7, y))[3] == 255
        assert image.getpixel((8, y))[3] == 0
    assert opaque_inside(image) == INSIDE_16 - {(x, y) for x in (6, 8) for y in range(1, 6)}


@pytest.mark.parametrize(
    ("percent", "fill", "outline"),
    [
        (100, DARK_PALETTE.ink, DARK_PALETTE.ink),
        (50, DARK_PALETTE.ink, DARK_PALETTE.ink),
        (49, DARK_PALETTE.caution, DARK_PALETTE.ink),
        (26, DARK_PALETTE.caution, DARK_PALETTE.ink),
        (25, DARK_PALETTE.critical, DARK_PALETTE.critical),
        (10, DARK_PALETTE.critical, DARK_PALETTE.critical),
    ],
)
def test_the_level_band_colors_the_mouse(
    percent: int, fill: tuple[int, int, int], outline: tuple[int, int, int]
) -> None:
    image = render(DeviceState.CONNECTED, percent)

    assert image.getpixel(BOTTOM_FILL_PIXEL) == (*fill, 255)
    assert image.getpixel(OUTLINE_PIXEL) == (*outline, 255)


def test_an_empty_battery_is_a_red_outline() -> None:
    image = render(DeviceState.CONNECTED, 0)

    assert image.getpixel(OUTLINE_PIXEL) == (*DARK_PALETTE.critical, 255)
    assert opaque_inside(image) == set()


def test_the_light_theme_uses_its_own_colors() -> None:
    full = render(DeviceState.CONNECTED, 85, theme=LIGHT)
    caution = render(DeviceState.CONNECTED, 30, theme=LIGHT)

    assert full.getpixel(OUTLINE_PIXEL) == (*LIGHT_PALETTE.ink, 255)
    assert caution.getpixel(BOTTOM_FILL_PIXEL) == (*LIGHT_PALETTE.caution, 255)


def test_charging_draws_the_whole_mouse_green() -> None:
    image = render(DeviceState.CHARGING, None)

    assert image.getpixel(OUTLINE_PIXEL) == (*DARK_PALETTE.charging, 255)
    assert image.getpixel(BOTTOM_FILL_PIXEL) == (*DARK_PALETTE.charging, 255)


def test_charging_fills_in_a_loop_starting_half_full() -> None:
    rows = [
        filled_rows(render(DeviceState.CHARGING, None, frame=frame))
        for frame in range(CHARGING_FRAMES)
    ]

    assert rows == [8, 10, 12, 14, 0, 2, 4, 6]
    wrapped = render(DeviceState.CHARGING, None, frame=CHARGING_FRAMES)
    assert wrapped.tobytes() == render(DeviceState.CHARGING, None, frame=0).tobytes()


def test_charging_ignores_the_frozen_level() -> None:
    frozen = render(DeviceState.CHARGING, 81)

    assert frozen.tobytes() == render(DeviceState.CHARGING, None).tobytes()


@pytest.mark.parametrize(
    ("state", "percent"),
    [
        (DeviceState.CONNECTED, 85),
        (DeviceState.ASLEEP, 42),
        (DeviceState.WAITING, None),
        (DeviceState.NO_RECEIVER, 63),
    ],
)
def test_other_states_ignore_the_frame(state: DeviceState, percent: int | None) -> None:
    assert render(state, percent, frame=3).tobytes() == render(state, percent).tobytes()


@pytest.mark.parametrize("theme", [DARK, LIGHT])
@pytest.mark.parametrize(
    ("state", "percent"),
    [
        (DeviceState.ASLEEP, 42),
        (DeviceState.ASLEEP, None),
        (DeviceState.WAITING, 42),
        (DeviceState.NO_RECEIVER, 63),
    ],
)
def test_inactive_states_are_dimmed_ink(
    theme: TaskbarTheme, state: DeviceState, percent: int | None
) -> None:
    palette = PALETTES[theme]
    image = render(state, percent, theme=theme)

    colors = {color for _, color in image.getcolors() if color[3]}
    assert colors == {(*palette.ink, alpha(palette.dim_alpha))}


def test_asleep_stipples_the_last_level() -> None:
    filled = opaque_inside(render(DeviceState.ASLEEP, 42))

    assert {y for _, y in filled} == set(range(9, 15))
    assert all((x + 1, y) not in filled for x, y in filled)


def test_asleep_without_a_level_shows_a_mark_below_the_wheel() -> None:
    marked = opaque_inside(render(DeviceState.ASLEEP, None))

    assert marked
    assert min(y for _, y in marked) > 5


@pytest.mark.parametrize("percent", [None, 42])
def test_waiting_shows_three_dots_and_no_level(percent: int | None) -> None:
    assert opaque_inside(render(DeviceState.WAITING, percent)) == {(5, 10), (7, 10), (9, 10)}


def test_no_receiver_slashes_through_the_mouse() -> None:
    image = render(DeviceState.NO_RECEIVER, None)

    assert MOUSE_16[4][12] == "#"
    assert image.getpixel((12, 4))[3] == 0
    assert image.getpixel((12, 3))[3]
    assert image.getpixel((7, 8))[3]
