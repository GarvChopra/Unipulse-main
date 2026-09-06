from db import locations


def test_seed_is_idempotent(memstore):
    locations.seed()
    n1 = len(locations.list_all())
    locations.seed()
    assert len(locations.list_all()) == n1
    assert n1 >= 10


def test_picker_shape(memstore):
    locations.seed()
    p = locations.picker()
    assert "GL Bajaj" in p["campus"]
    names = [n["name"] for n in p["nodes"]]
    assert "AB1" in names and "AB2" in names
    assert "Outer Area" in names
    ab1 = next(n for n in p["nodes"] if n["name"] == "AB1")
    assert any(f["name"] == "2nd Floor" for f in ab1["children"])
    outer = next(n for n in p["nodes"] if n["name"] == "Outer Area")
    assert any(z["name"] == "Security" for z in outer["children"])


def test_admin_can_add_room_under_floor(memstore):
    locations.seed()
    ab1 = next(c for c in locations.children(locations.campus_root()["id"]) if c["name"] == "AB1")
    floor = locations.children(ab1["id"])[0]
    room = locations.create("room", "204", parent_id=floor["id"], room_type="Classroom")
    assert room["id"] > 0
    assert room["room_type"] == "Classroom"
    assert room in locations.children(floor["id"])
