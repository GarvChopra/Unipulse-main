from db import locations


def test_seed_is_idempotent(memstore):
    locations.seed()
    n1 = len(locations.list_all())
    locations.seed()
    assert len(locations.list_all()) == n1
    assert n1 >= 10  # 5 types + 5 subzones minimum


def test_picker_shape(memstore):
    locations.seed()
    p = locations.picker()
    assert [t["name"] for t in p["types"]] == ["Academics Block", "Hostels", "Mess / Canteen",
                                               "Playground", "Outer Area"]
    assert "Security" in p["outer_area_subzones"]
    assert "Block A" in p["academics_blocks"]
    assert "2nd Floor" in p["academics_floors"]


def test_admin_can_add_block(memstore):
    locations.seed()
    loc = locations.create("block", "Block E", "Academics Block > Block E")
    assert loc["id"] > 0
    assert "Block E" in locations.picker()["academics_blocks"]
