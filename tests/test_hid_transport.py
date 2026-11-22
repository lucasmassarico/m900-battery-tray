from m900_battery_tray.hid_transport import (
    HidCollection,
    collection_from_entry,
    find_battery_collection,
)

BATTERY_PATH = b"\\\\?\\hid#vid_1d57&pid_fa65&mi_02&col03#7&abc&0&0002#{4d1e55b2}"
VENDOR_PATH = b"\\\\?\\hid#vid_1d57&pid_fa65&mi_02&col04#7&abc&0&0003#{4d1e55b2}"


def make_collection(
    product_id: int = 0xFA65, usage_page: int = 0x000A, usage: int = 0x00, path: bytes = b"p"
) -> HidCollection:
    return HidCollection(
        path=path,
        vendor_id=0x1D57,
        product_id=product_id,
        interface_number=2,
        usage_page=usage_page,
        usage=usage,
        product="2.4G 8K HS Receiver",
    )


def test_collection_from_entry_maps_hidapi_fields() -> None:
    entry = {
        "path": BATTERY_PATH,
        "vendor_id": 0x1D57,
        "product_id": 0xFA65,
        "serial_number": "",
        "release_number": 0x0100,
        "manufacturer_string": "LXDDZ",
        "product_string": "2.4G 8K HS Receiver",
        "usage_page": 0x000A,
        "usage": 0x00,
        "interface_number": 2,
    }

    assert collection_from_entry(entry) == HidCollection(
        path=BATTERY_PATH,
        vendor_id=0x1D57,
        product_id=0xFA65,
        interface_number=2,
        usage_page=0x000A,
        usage=0x00,
        product="2.4G 8K HS Receiver",
    )


def test_collection_from_entry_accepts_missing_product_string() -> None:
    entry = {
        "path": BATTERY_PATH,
        "vendor_id": 0x1D57,
        "product_id": 0xFA65,
        "product_string": None,
        "usage_page": 0x000A,
        "usage": 0x00,
        "interface_number": 2,
    }

    assert collection_from_entry(entry).product == ""


def test_find_battery_collection_picks_ordinal_page_and_skips_vendor_channel() -> None:
    mouse = make_collection(usage_page=0x0001, usage=0x02, path=b"mouse")
    vendor = make_collection(usage_page=0xFF00, usage=0x01, path=VENDOR_PATH)
    battery = make_collection(path=BATTERY_PATH)

    assert find_battery_collection([mouse, vendor, battery]) == battery


def test_find_battery_collection_ignores_other_products() -> None:
    wired = make_collection(product_id=0xFA60)

    assert find_battery_collection([wired]) is None


def test_find_battery_collection_returns_none_when_receiver_is_absent() -> None:
    assert find_battery_collection([]) is None
