import time

from db import grievances, users
from services.auth_service import hash_pin


def _reporter():
    return users.create("f1", "Faculty One", "reporter", hash_pin("1"))


def test_insert_sets_defaults(memstore):
    u = _reporter()
    g = grievances.insert(reporter_id=u["id"], reporter_name=u["display_name"],
                          title="Projector dead", description="Projector not working in the room",
                          location_type="academics_block",
                          location_label="Academics Block > Block B > 2nd Floor > Room 204")
    assert g["code"].startswith("GLB-CAMP-")
    assert g["status"] == "reported"
    assert g["priority_score"] == 0
    assert g["created_at"] == g["updated_at"]
    assert grievances.get_by_code(g["code"])["id"] == g["id"]


def test_list_for_reporter_newest_first(memstore):
    u = _reporter()
    a = grievances.insert(reporter_id=u["id"], reporter_name=u["display_name"], title="A",
                          description="desc one here", location_type="hostels",
                          location_label="Hostels")
    time.sleep(0.01)
    b = grievances.insert(reporter_id=u["id"], reporter_name=u["display_name"], title="B",
                          description="desc two here", location_type="hostels",
                          location_label="Hostels")
    got = grievances.list_for_reporter(u["id"])
    assert [x["code"] for x in got] == [b["code"], a["code"]]


def test_update_bumps_updated_at(memstore):
    u = _reporter()
    g = grievances.insert(reporter_id=u["id"], reporter_name="x", title="t",
                          description="description here now", location_type="playground",
                          location_label="Playground")
    time.sleep(0.01)
    g2 = grievances.update(g["id"], status="verified")
    assert g2["status"] == "verified"
    assert g2["updated_at"] > g["updated_at"]


def test_find_recurring_candidates_matches_label_and_category(memstore):
    u = _reporter()
    g1 = grievances.insert(reporter_id=u["id"], reporter_name="x", title="t1",
                           description="a leaking tap here", location_type="hostels",
                           location_label="Hostels", category="Plumbing")
    grievances.insert(reporter_id=u["id"], reporter_name="x", title="t2",
                      description="different one", location_type="hostels",
                      location_label="Hostels", category="Electric")
    hits = grievances.find_recurring_candidates("Hostels", "Plumbing", 0)
    assert [h["id"] for h in hits] == [g1["id"]]


def test_new_fields_default_and_persist(memstore):
    u = _reporter()
    g = grievances.insert(reporter_id=u["id"], reporter_name="x", title="t",
                          description="a description here now", location_type="hostels",
                          location_label="Hostels")
    assert g["noticed_at"] is None and g["affects_academics"] is False
    g2 = grievances.update(g["id"], noticed_at=123.0, affects_academics=True)
    assert g2["noticed_at"] == 123.0 and g2["affects_academics"] is True
