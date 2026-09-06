"""Phase 1 — real GL Bajaj location hierarchy (Campus → Building → Floor → Room,
plus standalone facilities). Structured, normalized, admin-expandable."""
from db import locations


# ── seed: verified GL Bajaj structure only, no invented rooms ──────────────

def test_seed_creates_campus_root(memstore):
    locations.seed()
    root = locations.campus_root()
    assert root is not None
    assert root["location_type"] == "campus"
    assert "GL Bajaj" in root["name"]


def test_seed_has_ab1_and_ab2_not_generic_blocks(memstore):
    locations.seed()
    buildings = [c["name"] for c in locations.children(locations.campus_root()["id"])
                 if c["location_type"] == "building"]
    assert "AB1" in buildings and "AB2" in buildings
    assert "Block A" not in buildings and "Block B" not in buildings


def test_seed_creates_no_rooms(memstore):
    locations.seed()
    assert [l for l in locations.list_all() if l["location_type"] == "room"] == []


def test_seed_buildings_have_floors(memstore):
    locations.seed()
    ab1 = next(c for c in locations.children(locations.campus_root()["id"]) if c["name"] == "AB1")
    floors = locations.children(ab1["id"])
    assert floors and all(f["location_type"] == "floor" for f in floors)


def test_seed_creates_named_canteens_and_facilities(memstore):
    locations.seed()
    tops = [c["name"] for c in locations.children(locations.campus_root()["id"])]
    for want in ("B.Tech Canteen", "MBA Canteen", "BCA Canteen", "Library",
                 "SHD Hall", "Hostels", "Playground", "Outer Area"):
        assert want in tops, want


def test_canteen_bucket_routes_as_mess(memstore):
    locations.seed()
    canteen = next(c for c in locations.children(locations.campus_root()["id"])
                   if c["name"] == "B.Tech Canteen")
    assert canteen["bucket"] == "mess_canteen"


def test_seed_is_idempotent(memstore):
    locations.seed()
    n1 = len(locations.list_all())
    locations.seed()
    assert len(locations.list_all()) == n1


# ── admin can extend the tree with real rooms later, no code change ────────

def test_admin_can_add_a_real_room_under_a_floor(memstore):
    locations.seed()
    ab2 = next(c for c in locations.children(locations.campus_root()["id"]) if c["name"] == "AB2")
    floor = locations.children(ab2["id"])[0]
    room = locations.create("room", "204", parent_id=floor["id"], room_type="Classroom")
    assert room["id"] > 0
    assert room["room_type"] == "Classroom"
    assert room["bucket"] == "academics_block"           # inherited from the building
    kids = locations.children(floor["id"])
    assert [k["name"] for k in kids] == ["204"]


def test_new_room_appears_in_picker(memstore):
    locations.seed()
    ab1 = next(c for c in locations.children(locations.campus_root()["id"]) if c["name"] == "AB1")
    floor = locations.children(ab1["id"])[0]
    locations.create("room", "G-01", parent_id=floor["id"], room_type="Lab")
    picker = locations.picker()
    ab1_node = next(n for n in picker["nodes"] if n["name"] == "AB1")
    floor_node = next(f for f in ab1_node["children"] if f["id"] == floor["id"])
    assert any(r["name"] == "G-01" and r["room_type"] == "Lab" for r in floor_node["children"])


def test_disabled_location_hidden_from_picker_but_kept(memstore):
    locations.seed()
    ab1 = next(c for c in locations.children(locations.campus_root()["id"]) if c["name"] == "AB1")
    locations.set_active(ab1["id"], False)
    assert all(n["name"] != "AB1" for n in locations.picker()["nodes"])
    assert any(l["name"] == "AB1" for l in locations.list_all(active_only=False))


# ── breadcrumb + denormalization for the grievance row ────────────────────

def test_breadcrumb_walks_the_tree(memstore):
    locations.seed()
    ab1 = next(c for c in locations.children(locations.campus_root()["id"]) if c["name"] == "AB1")
    floor = next(f for f in locations.children(ab1["id"]) if f["name"] == "2nd Floor")
    room = locations.create("room", "204", parent_id=floor["id"], room_type="Classroom")
    assert locations.breadcrumb(room["id"]) == "AB1 > 2nd Floor > 204"


def test_resolve_catalogued_room_fills_structured_fields(memstore):
    locations.seed()
    ab2 = next(c for c in locations.children(locations.campus_root()["id"]) if c["name"] == "AB2")
    floor = next(f for f in locations.children(ab2["id"]) if f["name"] == "1st Floor")
    room = locations.create("room", "112", parent_id=floor["id"], room_type="Faculty Room")
    r = locations.resolve_for_grievance(room["id"])
    assert r["location_type"] == "academics_block"
    assert r["block_no"] == "AB2"
    assert r["floor"] == "1st Floor"
    assert r["room"] == "112"
    assert r["location_label"] == "AB2 > 1st Floor > 112"
    assert r["location_id"] == room["id"]


def test_resolve_floor_with_free_text_room(memstore):
    """Room not catalogued yet: user picks the floor, types the number."""
    locations.seed()
    ab1 = next(c for c in locations.children(locations.campus_root()["id"]) if c["name"] == "AB1")
    floor = next(f for f in locations.children(ab1["id"]) if f["name"] == "Ground Floor")
    r = locations.resolve_for_grievance(floor["id"], room_free="G-17")
    assert r["block_no"] == "AB1"
    assert r["floor"] == "Ground Floor"
    assert r["room"] == "G-17"
    assert r["location_label"] == "AB1 > Ground Floor > G-17"


def test_resolve_facility_with_specific_area(memstore):
    locations.seed()
    canteen = next(c for c in locations.children(locations.campus_root()["id"])
                   if c["name"] == "MBA Canteen")
    r = locations.resolve_for_grievance(canteen["id"], area_free="Seating area")
    assert r["location_type"] == "mess_canteen"
    assert r["block_no"] == "MBA Canteen"
    assert r["sub_zone"] == "Seating area"
    assert r["location_label"] == "MBA Canteen > Seating area"


def test_resolve_outer_area_subzone(memstore):
    locations.seed()
    outer = next(c for c in locations.children(locations.campus_root()["id"]) if c["name"] == "Outer Area")
    sz = next(s for s in locations.children(outer["id"]) if s["name"] == "Security")
    r = locations.resolve_for_grievance(sz["id"])
    assert r["location_type"] == "outer_area"
    assert r["sub_zone"] == "Security"
    assert r["location_label"] == "Outer Area > Security"
