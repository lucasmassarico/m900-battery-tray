import json
from pathlib import Path
from typing import Any

import pytest

from m900_battery_tray.config import (
    Config,
    ConfigError,
    config_from_dict,
    config_to_dict,
    create_if_missing,
    default_config_path,
    load_or_create,
)

DEFAULTS = {
    "version": 1,
    "low_battery_percent": 20,
    "critical_battery_percent": 10,
    "sleep_after_seconds": 15,
}


def settings(**overrides: Any) -> dict[str, Any]:
    return {**DEFAULTS, **overrides}


def test_defaults() -> None:
    assert Config() == Config(
        low_battery_percent=20, critical_battery_percent=10, sleep_after_seconds=15
    )


def test_config_to_dict_includes_the_version() -> None:
    assert config_to_dict(Config()) == DEFAULTS


def test_config_from_dict_reads_every_setting() -> None:
    data = settings(low_battery_percent=30, critical_battery_percent=15, sleep_after_seconds=60)

    assert config_from_dict(data) == Config(
        low_battery_percent=30, critical_battery_percent=15, sleep_after_seconds=60
    )


def test_config_from_dict_uses_defaults_for_missing_settings() -> None:
    assert config_from_dict({"version": 1, "low_battery_percent": 25}) == Config(
        low_battery_percent=25
    )


@pytest.mark.parametrize("data", [[], "config", 1, None])
def test_config_from_dict_requires_an_object(data: object) -> None:
    with pytest.raises(ConfigError, match="must be a JSON object"):
        config_from_dict(data)


def test_config_from_dict_requires_the_version() -> None:
    data = settings()
    del data["version"]

    with pytest.raises(ConfigError, match="missing setting: version"):
        config_from_dict(data)


@pytest.mark.parametrize("version", [0, 2, "1", True])
def test_config_from_dict_rejects_other_versions(version: object) -> None:
    with pytest.raises(ConfigError, match="unsupported version"):
        config_from_dict(settings(version=version))


def test_config_from_dict_rejects_unknown_settings() -> None:
    with pytest.raises(ConfigError, match="unknown setting: low_battery"):
        config_from_dict(settings(low_battery=20))


@pytest.mark.parametrize("value", [True, 20.0, 20.5, "20", None])
def test_config_from_dict_requires_whole_numbers(value: object) -> None:
    with pytest.raises(ConfigError, match="low_battery_percent must be a whole number"):
        config_from_dict(settings(low_battery_percent=value))


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"critical_battery_percent": 0}, "critical_battery_percent must be between 1 and 98"),
        ({"low_battery_percent": 100}, "low_battery_percent must be between 2 and 99"),
        ({"low_battery_percent": 1}, "low_battery_percent must be between 2 and 99"),
        ({"low_battery_percent": 10}, "must be lower than low_battery_percent"),
        ({"critical_battery_percent": 30}, "must be lower than low_battery_percent"),
        ({"sleep_after_seconds": 11}, "sleep_after_seconds must be between 12 and 3600"),
        ({"sleep_after_seconds": 3601}, "sleep_after_seconds must be between 12 and 3600"),
    ],
)
def test_config_from_dict_rejects_out_of_range_values(
    overrides: dict[str, int], message: str
) -> None:
    with pytest.raises(ConfigError, match=message):
        config_from_dict(settings(**overrides))


@pytest.mark.parametrize(
    "overrides",
    [
        {"low_battery_percent": 2, "critical_battery_percent": 1},
        {"low_battery_percent": 99, "critical_battery_percent": 98},
        {"sleep_after_seconds": 12},
        {"sleep_after_seconds": 3600},
    ],
)
def test_config_from_dict_accepts_boundary_values(overrides: dict[str, int]) -> None:
    config_from_dict(settings(**overrides))


def test_config_rejects_invalid_values_when_built_directly() -> None:
    with pytest.raises(ConfigError, match="must be lower than low_battery_percent"):
        Config(low_battery_percent=10, critical_battery_percent=10)


def test_default_config_path_is_under_appdata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))

    assert default_config_path() == tmp_path / "m900-battery-tray" / "config.json"


def test_load_or_create_writes_defaults_when_the_file_is_missing(tmp_path: Path) -> None:
    path = tmp_path / "m900-battery-tray" / "config.json"

    assert load_or_create(path) == Config()
    assert json.loads(path.read_text(encoding="utf-8")) == DEFAULTS


def test_load_or_create_reads_an_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps(settings(low_battery_percent=35)), encoding="utf-8")

    assert load_or_create(path) == Config(low_battery_percent=35)


def test_load_or_create_accepts_a_utf8_bom(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps(settings(sleep_after_seconds=30)), encoding="utf-8-sig")

    assert load_or_create(path) == Config(sleep_after_seconds=30)


def test_load_or_create_reports_broken_json_and_keeps_the_file(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    broken = '{\n  "version": 1,\n  "low_battery_percent": 20,\n}\n'
    path.write_text(broken, encoding="utf-8")

    with pytest.raises(ConfigError, match=r"config\.json: invalid JSON at line \d+ column \d+"):
        load_or_create(path)
    assert path.read_text(encoding="utf-8") == broken


def test_load_or_create_reports_invalid_settings_and_keeps_the_file(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    content = json.dumps(settings(sleep_after_seconds=1))
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ConfigError, match=r"config\.json: sleep_after_seconds must be between"):
        load_or_create(path)
    assert path.read_text(encoding="utf-8") == content


def test_load_or_create_reports_a_file_it_cannot_read(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def deny(self: Path, encoding: str) -> str:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(Path, "read_text", deny)

    with pytest.raises(ConfigError, match=r"cannot read the file \(Permission denied\)"):
        load_or_create(tmp_path / "config.json")


def test_load_or_create_reports_a_file_that_is_not_utf8(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_bytes(b'{"version": 1, "low_battery_percent": \xff}')

    with pytest.raises(ConfigError, match="not valid UTF-8"):
        load_or_create(path)


def test_create_if_missing_writes_the_defaults(tmp_path: Path) -> None:
    path = tmp_path / "m900-battery-tray" / "config.json"

    create_if_missing(path)

    assert json.loads(path.read_text(encoding="utf-8")) == DEFAULTS


def test_create_if_missing_keeps_an_existing_file_even_if_broken(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{", encoding="utf-8")

    create_if_missing(path)

    assert path.read_text(encoding="utf-8") == "{"
