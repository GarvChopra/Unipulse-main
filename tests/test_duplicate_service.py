import time

from db import grievances, users
from services import duplicate_service as ds
from services.auth_service import hash_pin


def _mk(reporter_id, label, category, created_offset_days=0.0):
    g = grievances.insert(reporter_id=reporter_id, reporter_name="x", title="t",
                          description="a broken thing here now", location_type="hostels",
                          location_label=label, category=category)
    if created_offset_days:
        grievances.update(g["id"], created_at=time.time() - created_offset_days * 86400)
    return g


def test_no_category_never_matches(memstore):
    u = users.create("a", "A", "reporter", hash_pin("1"))
    _mk(u["id"], "Hostels", None)
    r = ds.find_recurring("Hostels", None, u["id"])
    assert r == {"same_reporter_recent": False, "candidates": [], "match": False}


def test_different_reporter_same_place_and_category_matches(memstore):
    u1 = users.create("u1", "U1", "reporter", hash_pin("1"))
    u2 = users.create("u2", "U2", "reporter", hash_pin("1"))
    _mk(u1["id"], "Hostels", "Plumbing")
    r = ds.find_recurring("Hostels", "Plumbing", u2["id"])
    assert r["match"] is True
    assert len(r["candidates"]) == 1
    assert r["same_reporter_recent"] is False


def test_same_reporter_within_24h_is_true_duplicate(memstore):
    u = users.create("u", "U", "reporter", hash_pin("1"))
    _mk(u["id"], "Playground", "Civil")
    r = ds.find_recurring("Playground", "Civil", u["id"])
    assert r["same_reporter_recent"] is True
    assert r["match"] is False


def test_outside_window_no_match(memstore):
    u1 = users.create("u1", "U1", "reporter", hash_pin("1"))
    u2 = users.create("u2", "U2", "reporter", hash_pin("1"))
    _mk(u1["id"], "Mess / Canteen", "Mechanical", created_offset_days=20)
    r = ds.find_recurring("Mess / Canteen", "Mechanical", u2["id"])
    assert r["candidates"] == []
    assert r["match"] is False
