"""Build the Windows app folder with PyInstaller and zip it.

Usage: python scripts/build_exe.py   (needs the "build" extra: pip install -e ".[build]")

Output: dist/m900-battery-tray/m900-battery-tray.exe, plus the folder zipped as
dist/m900-battery-tray-<version>-win64.zip. The exe has no console window; started from a
terminal with arguments (e.g. --probe) it prints to that terminal.
"""

import shutil
from importlib.metadata import version
from pathlib import Path

import PyInstaller.__main__
from PIL import Image

from m900_battery_tray.icon import CHARGING_FRAMES, TaskbarTheme, render_icon
from m900_battery_tray.state import DeviceState, Snapshot

NAME = "m900-battery-tray"
ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
DIST = ROOT / "dist"
ENTRY = ROOT / "src" / "m900_battery_tray" / "__main__.py"

# The full green mouse: it reads on both light and dark Explorer backgrounds.
FULL_FRAME = CHARGING_FRAMES // 2 - 1
DRAWN_SIZES = (16, 20, 24, 32)
# Explorer's larger views get the 24 and 32 px drawings scaled up by whole steps.
SCALED_SIZES = {48: 24, 64: 32, 256: 32}


def write_exe_icon(path: Path) -> None:
    snapshot = Snapshot(state=DeviceState.CHARGING, percent=None)

    def drawn(size: int) -> Image.Image:
        return render_icon(snapshot, size, TaskbarTheme.DARK, frame=FULL_FRAME)

    images = [drawn(size) for size in DRAWN_SIZES]
    images += [
        drawn(source).resize((size, size), Image.Resampling.NEAREST)
        for size, source in SCALED_SIZES.items()
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    images[-1].save(path, sizes=[image.size for image in images], append_images=images[:-1])


def main() -> None:
    icon_path = BUILD / f"{NAME}.ico"
    write_exe_icon(icon_path)
    PyInstaller.__main__.run(
        [
            str(ENTRY),
            f"--name={NAME}",
            "--onedir",
            "--windowed",
            f"--icon={icon_path}",
            f"--paths={ROOT / 'src'}",
            f"--distpath={DIST}",
            f"--workpath={BUILD / 'pyinstaller'}",
            f"--specpath={BUILD}",
            "--noconfirm",
            "--clean",
        ]
    )
    archive = DIST / f"{NAME}-{version(NAME)}-win64"
    shutil.make_archive(str(archive), "zip", root_dir=DIST, base_dir=NAME)
    print(f"built {DIST / NAME} and {archive}.zip")


if __name__ == "__main__":
    main()
