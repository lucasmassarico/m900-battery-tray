import os
from pathlib import Path

import pytest

from m900_battery_tray.config import Config, ConfigError
from m900_battery_tray.settings_watcher import SettingsWatcher

DEFAULT_FILE = '{"version": 1}'
FIRST_SAVE_NS = 2_000_000_000


class Recorder:
    def __init__(self) -> None:
        self.applied: list[Config] = []
        self.rejected: list[ConfigError] = []

    def apply(self, config: Config) -> None:
        self.applied.append(config)

    def reject(self, error: ConfigError) -> None:
        self.rejected.append(error)


class StopAfter:
    def __init__(self, polls: int) -> None:
        self.polls = polls

    def is_set(self) -> bool:
        return self.polls <= 0

    def wait(self, timeout: float) -> bool:
        self.polls -= 1
        return self.polls < 0


def save(path: Path, text: str, at_ns: int) -> None:
    path.write_text(text, encoding="utf-8")
    os.utime(path, ns=(at_ns, at_ns))


@pytest.fixture
def path(tmp_path: Path) -> Path:
    path = tmp_path / "config.json"
    save(path, DEFAULT_FILE, 1_000_000_000)
    return path


def watch(path: Path) -> tuple[SettingsWatcher, Recorder]:
    recorder = Recorder()
    return SettingsWatcher(path, recorder.apply, recorder.reject), recorder


def test_an_unchanged_file_is_not_reloaded(path: Path) -> None:
    watcher, recorder = watch(path)

    watcher.check()
    watcher.check()

    assert recorder.applied == []
    assert recorder.rejected == []


def test_a_saved_file_is_applied_once_after_it_settles(path: Path) -> None:
    watcher, recorder = watch(path)
    save(path, '{"version": 1, "low_battery_percent": 30}', FIRST_SAVE_NS)

    watcher.check()
    assert recorder.applied == []
    watcher.check()
    watcher.check()

    assert recorder.applied == [Config(low_battery_percent=30)]


def test_a_save_still_in_progress_is_not_read(path: Path) -> None:
    watcher, recorder = watch(path)
    save(path, "", FIRST_SAVE_NS)
    watcher.check()
    save(path, '{"version": 1, "sleep_after_seconds": 40}', FIRST_SAVE_NS + 1)

    watcher.check()
    watcher.check()

    assert recorder.rejected == []
    assert recorder.applied == [Config(sleep_after_seconds=40)]


def test_a_broken_file_is_rejected_once_and_a_fix_is_applied(path: Path) -> None:
    watcher, recorder = watch(path)
    save(path, "{", FIRST_SAVE_NS)
    for _ in range(3):
        watcher.check()

    save(path, '{"version": 1, "critical_battery_percent": 5}', FIRST_SAVE_NS + 1)
    watcher.check()
    watcher.check()

    assert len(recorder.rejected) == 1
    assert str(recorder.rejected[0]).startswith(f"{path}: invalid JSON at line 1 column 2")
    assert recorder.applied == [Config(critical_battery_percent=5)]


def test_a_missing_file_is_ignored_until_it_comes_back(path: Path) -> None:
    watcher, recorder = watch(path)
    path.unlink()
    watcher.check()
    watcher.check()
    assert recorder.applied == []
    assert not path.exists()

    save(path, '{"version": 1, "low_battery_percent": 25}', FIRST_SAVE_NS)
    watcher.check()
    watcher.check()

    assert recorder.applied == [Config(low_battery_percent=25)]


def test_run_polls_until_stopped_and_survives_a_failing_apply(path: Path) -> None:
    calls: list[Config] = []

    def failing_apply(config: Config) -> None:
        calls.append(config)
        raise RuntimeError("display gone")

    watcher = SettingsWatcher(path, failing_apply, lambda error: None)
    save(path, '{"version": 1, "low_battery_percent": 30}', FIRST_SAVE_NS)

    watcher.run(StopAfter(polls=3))

    assert calls == [Config(low_battery_percent=30)]
