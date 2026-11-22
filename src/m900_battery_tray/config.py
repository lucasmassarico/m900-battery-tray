"""User settings, stored as JSON in %APPDATA%\\m900-battery-tray\\config.json."""

import contextlib
import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

APP_DIR_NAME = "m900-battery-tray"
CONFIG_FILE_NAME = "config.json"
CONFIG_VERSION = 1

CRITICAL_PERCENT_RANGE = (1, 98)
LOW_PERCENT_RANGE = (2, 99)
# A dozing mouse reports every 4 s; anything shorter than three reports would flicker to "asleep".
SLEEP_SECONDS_RANGE = (12, 3600)


class ConfigError(ValueError):
    """The settings file can't be used. The message says why, in user-facing words."""


@dataclass(frozen=True)
class Config:
    low_battery_percent: int = 20
    critical_battery_percent: int = 10
    sleep_after_seconds: int = 15

    def __post_init__(self) -> None:
        _require_range(
            "critical_battery_percent", self.critical_battery_percent, CRITICAL_PERCENT_RANGE
        )
        _require_range("low_battery_percent", self.low_battery_percent, LOW_PERCENT_RANGE)
        if self.critical_battery_percent >= self.low_battery_percent:
            raise ConfigError(
                f"critical_battery_percent ({self.critical_battery_percent}) must be lower than "
                f"low_battery_percent ({self.low_battery_percent})"
            )
        _require_range("sleep_after_seconds", self.sleep_after_seconds, SLEEP_SECONDS_RANGE)


_SETTING_NAMES = tuple(field.name for field in fields(Config))


def default_config_path() -> Path:
    return Path(os.environ["APPDATA"]) / APP_DIR_NAME / CONFIG_FILE_NAME


def config_to_dict(config: Config) -> dict[str, int]:
    return {"version": CONFIG_VERSION, **asdict(config)}


def config_from_dict(data: object) -> Config:
    """Validate decoded JSON and build a Config. Missing settings take their defaults."""
    if not isinstance(data, dict):
        raise ConfigError("the config must be a JSON object")
    unknown = sorted(set(data) - {"version", *_SETTING_NAMES})
    if unknown:
        raise ConfigError(f"unknown setting: {', '.join(unknown)}")
    if "version" not in data:
        raise ConfigError("missing setting: version")
    version = data["version"]
    if not _is_whole_number(version) or version != CONFIG_VERSION:
        raise ConfigError(f"unsupported version {version!r} (expected {CONFIG_VERSION})")

    values: dict[str, int] = {}
    for name in _SETTING_NAMES:
        if name not in data:
            continue
        value = data[name]
        if not _is_whole_number(value):
            raise ConfigError(f"{name} must be a whole number, got {value!r}")
        values[name] = value
    return Config(**values)


def load_or_create(path: Path) -> Config:
    """Load the settings file, creating it with the defaults if it doesn't exist.

    Raises ConfigError if the file exists but can't be used. The file is never overwritten,
    so the user's edits survive a mistake.
    """
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        config = Config()
        _write_new(path, config)
        return config
    except UnicodeDecodeError:
        raise ConfigError(f"{path}: the file is not valid UTF-8") from None
    except OSError as error:
        raise ConfigError(f"{path}: cannot read the file ({error.strerror})") from error

    try:
        data: Any = json.loads(text)
    except json.JSONDecodeError as error:
        raise ConfigError(
            f"{path}: invalid JSON at line {error.lineno} column {error.colno} ({error.msg})"
        ) from None
    try:
        return config_from_dict(data)
    except ConfigError as error:
        raise ConfigError(f"{path}: {error}") from None


def create_if_missing(path: Path) -> None:
    """Write the default settings file unless one already exists (valid or not)."""
    with contextlib.suppress(FileExistsError):
        _write_new(path, Config())


def _write_new(path: Path, config: Config) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as file:
        json.dump(config_to_dict(config), file, indent=2)
        file.write("\n")


def _is_whole_number(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require_range(name: str, value: int, bounds: tuple[int, int]) -> None:
    low, high = bounds
    if not low <= value <= high:
        raise ConfigError(f"{name} must be between {low} and {high}, got {value}")
