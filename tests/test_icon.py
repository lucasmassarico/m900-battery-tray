import pytest
from PIL import Image

from m900_battery_tray.icon import PALETTES, TaskbarTheme, render_icon
from m900_battery_tray.state import DeviceState, Snapshot

DARK = TaskbarTheme.DARK
LIGHT = TaskbarTheme.LIGHT
DARK_PALETTE = PALETTES[DARK]
LIGHT_PALETTE = PALETTES[LIGHT]

# 16 px layout: digits on rows 1-7, gauge box on rows 10-14 (inside rows 11-13).
DIGIT_ROWS = range(1, 8)
GAUGE_INSIDE_ROWS = range(11, 14)


def render(
    state: DeviceState,
    percent: int | None,
    size: int = 16,
    theme: TaskbarTheme = DARK,
    low: int = 20,
    critical: int = 10,
) -> Image.Image:
    return render_icon(
        Snapshot(state=state, percent=percent),
        size,
        theme,
        low_percent=low,
        critical_percent=critical,
    )


def opaque_mask(image: Image.Image, rows: range) -> list[str]:
    return [
        "".join("#" if image.getpixel((x, y))[3] else "." for x in range(image.width)) for y in rows
    ]


def alpha(level: float) -> int:
    return int(round(255 * level))


@pytest.mark.parametrize("size", [16, 20, 24, 32])
def test_renders_a_transparent_square_of_the_requested_size(size: int) -> None:
    image = render(DeviceState.CONNECTED, 85, size=size)

    assert image.mode == "RGBA"
    assert image.size == (size, size)
    assert image.getpixel((0, 0))[3] == 0


def test_sizes_between_layouts_use_the_smaller_layout() -> None:
    assert render(DeviceState.CONNECTED, 85, size=28).size == (28, 28)


@pytest.mark.parametrize("size", range(16, 41))
@pytest.mark.parametrize("state", list(DeviceState))
@pytest.mark.parametrize("percent", [None, 0, 7, 100])
def test_every_state_fits_every_size(size: int, state: DeviceState, percent: int | None) -> None:
    assert render(state, percent, size=size).size == (size, size)


def test_sizes_below_16_are_rejected() -> None:
    with pytest.raises(ValueError, match="at least 16"):
        render(DeviceState.CONNECTED, 85, size=15)


def test_100_fits_in_16_px() -> None:
    image = render(DeviceState.CONNECTED, 100)

    assert opaque_mask(image, DIGIT_ROWS) == [
        "...#...##...##..",
        "..##..#..#.#..#.",
        "...#..#..#.#..#.",
        "...#..#..#.#..#.",
        "...#..#..#.#..#.",
        "...#..#..#.#..#.",
        "..###..##...##..",
    ]


def test_digits_are_centered() -> None:
    image = render(DeviceState.CONNECTED, 85)

    assert opaque_mask(image, range(1, 2)) == [".....##..####..."]


@pytest.mark.parametrize(
    ("percent", "filled_columns"),
    [(0, 0), (1, 1), (50, 6), (85, 11), (100, 13)],
)
def test_the_gauge_fills_in_proportion(percent: int, filled_columns: int) -> None:
    image = render(DeviceState.CONNECTED, percent)

    expected = "#" + "#" * filled_columns + "." * (13 - filled_columns)
    for row in opaque_mask(image, GAUGE_INSIDE_ROWS):
        assert row[0:14] == expected


def test_normal_level_draws_in_ink() -> None:
    image = render(DeviceState.CONNECTED, 85)

    assert image.getpixel((5, 1)) == (*DARK_PALETTE.ink, 255)
    assert image.getpixel((0, 10)) == (*DARK_PALETTE.ink, alpha(0.75))


@pytest.mark.parametrize(
    ("percent", "theme", "color"),
    [
        (18, DARK, DARK_PALETTE.low),
        (7, DARK, DARK_PALETTE.critical),
        (18, LIGHT, LIGHT_PALETTE.low),
        (7, LIGHT, LIGHT_PALETTE.critical),
    ],
)
def test_low_and_critical_levels_color_digits_fill_and_outline(
    percent: int, theme: TaskbarTheme, color: tuple[int, int, int]
) -> None:
    image = render(DeviceState.CONNECTED, percent, theme=theme)
    digit = next((x, y) for y in DIGIT_ROWS for x in range(16) if image.getpixel((x, y))[3])

    assert image.getpixel(digit) == (*color, 255)
    assert image.getpixel((1, 11)) == (*color, 255)
    assert image.getpixel((0, 10)) == (*color, alpha(0.85))


def test_thresholds_come_from_the_caller() -> None:
    image = render(DeviceState.CONNECTED, 25, low=30, critical=15)

    assert image.getpixel((1, 11)) == (*DARK_PALETTE.low, 255)


def test_the_light_theme_uses_dark_ink() -> None:
    image = render(DeviceState.CONNECTED, 85, theme=LIGHT)

    assert image.getpixel((5, 1)) == (*LIGHT_PALETTE.ink, 255)


def test_charging_draws_a_bolt_instead_of_the_nub() -> None:
    image = render(DeviceState.CHARGING, 64)

    assert opaque_mask(image, range(10, 15)) == [
        "###########...##",
        "#######...#..##.",
        "#######...#..###",
        "#######...#...#.",
        "###########..#..",
    ]
    assert image.getpixel((14, 10)) == (*DARK_PALETTE.charging, 255)
    assert image.getpixel((1, 11)) == (*DARK_PALETTE.charging, 255)


def test_charging_never_uses_the_alarm_colors() -> None:
    image = render(DeviceState.CHARGING, 5)

    assert image.getpixel((1, 11)) == (*DARK_PALETTE.charging, 255)
    assert image.getpixel((0, 10)) == (*DARK_PALETTE.ink, alpha(0.75))


@pytest.mark.parametrize("theme", [DARK, LIGHT])
def test_asleep_is_dimmed_and_stippled(theme: TaskbarTheme) -> None:
    image = render(DeviceState.ASLEEP, 100, theme=theme)
    dim = PALETTES[theme].dim_alpha

    assert image.getpixel((3, 1)) == (*PALETTES[theme].ink, alpha(dim))
    assert image.getpixel((0, 10)) == (*PALETTES[theme].ink, alpha(0.75 * dim))
    assert opaque_mask(image, GAUGE_INSIDE_ROWS) == [
        "##.#.#.#.#.#.##.",
        "#.#.#.#.#.#.#.##",
        "##.#.#.#.#.#.##.",
    ]


def test_an_unknown_level_shows_two_dashes_and_no_fill() -> None:
    image = render(DeviceState.ASLEEP, None)

    assert opaque_mask(image, range(4, 5)) == ["....####.####..."]
    assert opaque_mask(image, GAUGE_INSIDE_ROWS) == [
        "#.............#.",
        "#.............##",
        "#.............#.",
    ]


def test_waiting_shows_three_dots_and_no_fill() -> None:
    image = render(DeviceState.WAITING, 42)

    assert opaque_mask(image, GAUGE_INSIDE_ROWS) == [
        "#.............#.",
        "#..#...#...#..##",
        "#.............#.",
    ]
    assert image.getpixel((3, 12)) == (*DARK_PALETTE.ink, alpha(DARK_PALETTE.dim_alpha))


def test_no_receiver_shows_a_cross_without_the_gauge() -> None:
    image = render(DeviceState.NO_RECEIVER, 63)

    assert opaque_mask(image, range(10, 15)) == [
        ".....#...#......",
        "......#.#.......",
        ".......#........",
        "......#.#.......",
        ".....#...#......",
    ]
    assert image.getpixel((7, 12)) == (*DARK_PALETTE.ink, alpha(DARK_PALETTE.dim_alpha))
