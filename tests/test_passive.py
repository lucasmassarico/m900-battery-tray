"""Guards for the passive-read rule: the app must never send anything to the receiver."""

import ast
from pathlib import Path

import m900_battery_tray

PACKAGE_DIR = Path(m900_battery_tray.__file__).parent
HIDAPI_ADAPTER = PACKAGE_DIR / "hidapi_transport.py"

# hidapi device methods that send a report or a request to the device.
FORBIDDEN_DEVICE_CALLS = {
    "write",
    "send_feature_report",
    "get_feature_report",
    "get_input_report",
    "send_output_report",
}


def called_attribute_names(source: Path) -> set[str]:
    tree = ast.parse(source.read_text(encoding="utf-8"))
    return {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }


def imported_modules(source: Path) -> set[str]:
    tree = ast.parse(source.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_hidapi_adapter_never_sends_reports() -> None:
    assert called_attribute_names(HIDAPI_ADAPTER).isdisjoint(FORBIDDEN_DEVICE_CALLS)


def test_only_the_adapter_imports_hidapi() -> None:
    importers = {
        source.name for source in PACKAGE_DIR.rglob("*.py") if "hid" in imported_modules(source)
    }

    assert importers == {HIDAPI_ADAPTER.name}
