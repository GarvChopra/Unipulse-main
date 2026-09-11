"""The admin queue's sort control (Priority / Newest / Due date) must actually
re-order the rows — a regression where the endpoint always sorted by priority."""
import time

from db import grievances as gdb
from services import grievance_service as gs


def _report(client, user, desc, created_at=None):
    c = client.application.test_client()
    c.post("/login", data={"username": user, "pin": "1234"})
    out = c.post("/report", json={
        "description": desc, "location_type": "hostels", "location_label": "Hostels",
        "photo_b64": "aGVsbG8=", "photo_mime": "image/jpeg"}).get_json()
    g = gdb.get_by_code(out["code"])
    if created_at is not None:
        gdb.update(g["id"], created_at=created_at)
    return out["code"], g["id"]


def test_newest_sort_puts_the_latest_report_first(client):
    now = time.time()
    # Severity is AI/keyword-decided (not form-supplied), so the wording
    # itself is what drives "high" vs "low" here.
    old_code, _ = _report(client, "prof.rao",
                           "An old dangerous exposed wire issue reported a while ago here",
                           created_at=now - 10 * 86400)
    new_code, _ = _report(client, "dr.iyer",
                          "A brand new minor cosmetic issue just reported right now here",
                          created_at=now)

    client.post("/login", data={"username": "admin", "pin": "0000"})
    rows = client.get("/admin/grievances/data?sort=created").get_json()["rows"]
    assert rows[0]["code"] == new_code, [r["code"] for r in rows]

    # priority sort still leads with the high-severity one
    rows_p = client.get("/admin/grievances/data?sort=priority").get_json()["rows"]
    assert rows_p[0]["code"] == old_code


def test_due_date_sort_orders_by_soonest_due(client):
    c1, id1 = _report(client, "prof.rao", "Issue one that will be assigned first here now")
    c2, id2 = _report(client, "prof.khan", "Issue two assigned with a later due date here")
    client.post("/login", data={"username": "admin", "pin": "0000"})
    for code in (c1, c2):
        client.post(f"/admin/grievances/{code}/verify")
    g1 = gdb.get_by_code(c1); g2 = gdb.get_by_code(c2)
    gs.assign(g1["id"], unit="Infrastructure", assignee="a", actor="admin",
              due_at=time.time() + 5 * 86400)
    gs.assign(g2["id"], unit="Infrastructure", assignee="b", actor="admin",
              due_at=time.time() + 1 * 86400)
    rows = client.get("/admin/grievances/data?sort=due").get_json()["rows"]
    codes = [r["code"] for r in rows if r["code"] in (c1, c2)]
    assert codes == [c2, c1]
