import contextlib
import sys
import uuid
from collections.abc import Iterator

import pytest

from m900_battery_tray.autostart import RegistryAutostart, launch_command

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows registry")

TEST_ROOT = r"Software\m900-battery-tray-tests"


@pytest.fixture
def autostart() -> Iterator[RegistryAutostart]:
    import winreg

    key_path = rf"{TEST_ROOT}\{uuid.uuid4().hex}"
    yield RegistryAutostart(key_path=key_path, value_name="M900BatteryTray")
    for path in (key_path, TEST_ROOT):
        with contextlib.suppress(OSError):
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)


def test_launch_command_for_the_packaged_exe() -> None:
    command = launch_command(r"C:\Apps\M900 Battery Tray\m900-battery-tray.exe", frozen=True)

    assert command == r'"C:\Apps\M900 Battery Tray\m900-battery-tray.exe"'


def test_launch_command_from_source_uses_pythonw() -> None:
    command = launch_command(r"C:\Projects\tray\.venv\Scripts\python.exe", frozen=False)

    assert command == r'"C:\Projects\tray\.venv\Scripts\pythonw.exe" -m m900_battery_tray'


def test_disabled_by_default(autostart: RegistryAutostart) -> None:
    assert not autostart.is_enabled()
    assert autostart.command() is None


def test_enable_writes_the_command(autostart: RegistryAutostart) -> None:
    autostart.enable('"C:\\app.exe"')

    assert autostart.is_enabled()
    assert autostart.command() == '"C:\\app.exe"'


def test_disable_removes_the_command(autostart: RegistryAutostart) -> None:
    autostart.enable('"C:\\app.exe"')

    autostart.disable()

    assert not autostart.is_enabled()


def test_disable_when_already_disabled_does_nothing(autostart: RegistryAutostart) -> None:
    autostart.disable()

    assert not autostart.is_enabled()


def test_keep_current_rewrites_a_stale_command(autostart: RegistryAutostart) -> None:
    autostart.enable('"C:\\old\\app.exe"')

    autostart.keep_current('"C:\\new\\app.exe"')

    assert autostart.command() == '"C:\\new\\app.exe"'


def test_keep_current_leaves_a_disabled_autostart_alone(autostart: RegistryAutostart) -> None:
    autostart.keep_current('"C:\\new\\app.exe"')

    assert not autostart.is_enabled()
