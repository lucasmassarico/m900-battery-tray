"""Read-only HID access, kept behind a small interface so it can be faked in tests.

The interface deliberately has no write method: battery reading is passive and the app
must never send output or feature reports to the receiver (see docs/research.md).
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

RECEIVER_VENDOR_ID = 0x1D57
RECEIVER_PRODUCT_ID = 0xFA65
WIRED_PRODUCT_ID = 0xFA60
BATTERY_USAGE_PAGE = 0x000A


@dataclass(frozen=True)
class HidCollection:
    path: bytes
    vendor_id: int
    product_id: int
    interface_number: int
    usage_page: int
    usage: int
    product: str


class HidReader(Protocol):
    def read(self, size: int, timeout_ms: int) -> bytes:
        """Return one input report, or b"" on timeout. Raise OSError if the device is gone."""
        ...

    def close(self) -> None: ...


class HidTransport(Protocol):
    def enumerate(self, vendor_id: int, product_id: int) -> list[HidCollection]: ...

    def open(self, path: bytes) -> HidReader: ...


def collection_from_entry(entry: Mapping[str, Any]) -> HidCollection:
    return HidCollection(
        path=entry["path"],
        vendor_id=entry["vendor_id"],
        product_id=entry["product_id"],
        interface_number=entry["interface_number"],
        usage_page=entry["usage_page"],
        usage=entry["usage"],
        product=entry.get("product_string") or "",
    )


def find_battery_collection(collections: Iterable[HidCollection]) -> HidCollection | None:
    """Pick the receiver collection that carries the battery frames (MI_02/COL03)."""
    for collection in collections:
        if (
            collection.vendor_id == RECEIVER_VENDOR_ID
            and collection.product_id == RECEIVER_PRODUCT_ID
            and collection.usage_page == BATTERY_USAGE_PAGE
        ):
            return collection
    return None
