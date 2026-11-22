"""'Start with Windows': a value under HKCU\\...\\CurrentVersion\\Run, per user, no admin."""

import winreg
from pathlib import PureWindowsPath

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "M900BatteryTray"


def launch_command(executable: str, frozen: bool) -> str:
    """The command Windows runs at sign-in: the packaged exe, or pythonw (no console window)."""
    if frozen:
        return f'"{executable}"'
    pythonw = PureWindowsPath(executable).with_name("pythonw.exe")
    return f'"{pythonw}" -m m900_battery_tray'


class RegistryAutostart:
    def __init__(self, key_path: str = RUN_KEY, value_name: str = VALUE_NAME) -> None:
        self._key_path = key_path
        self._value_name = value_name

    def command(self) -> str | None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._key_path) as key:
                value, _ = winreg.QueryValueEx(key, self._value_name)
        except FileNotFoundError:
            return None
        return str(value)

    def is_enabled(self) -> bool:
        return self.command() is not None

    def enable(self, command: str) -> None:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, self._key_path, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, self._value_name, 0, winreg.REG_SZ, command)

    def disable(self) -> None:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, self._key_path, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.DeleteValue(key, self._value_name)
        except FileNotFoundError:
            pass

    def keep_current(self, command: str) -> None:
        """If autostart is on but points somewhere else (the app was moved), point it here."""
        current = self.command()
        if current is not None and current != command:
            self.enable(command)
