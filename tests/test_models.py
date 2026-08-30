from domain.models import build_location_label, recurring_key

_NAMES = {"academics_block": "Academics Block", "hostels": "Hostels",
          "mess_canteen": "Mess / Canteen", "playground": "Playground",
          "outer_area": "Outer Area"}


def test_location_label_academics_full():
    got = build_location_label("academics_block", "Block B", "2nd Floor", "204", None,
                               type_names=_NAMES)
    assert got == "Academics Block > Block B > 2nd Floor > Room 204"


def test_location_label_outer_area():
    got = build_location_label("outer_area", None, None, None, "Security", type_names=_NAMES)
    assert got == "Outer Area > Security"


def test_location_label_flat():
    assert build_location_label("playground", None, None, None, None, type_names=_NAMES) == "Playground"


def test_recurring_key_is_normalised():
    assert recurring_key("  Academics Block > Block B > 2nd Floor > Room 204 ", "Electric") \
        == "academics block > block b > 2nd floor > room 204|electric"
