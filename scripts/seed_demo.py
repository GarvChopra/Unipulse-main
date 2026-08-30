"""Realistic demo campus data for UniPulse. Idempotent. Run: python scripts/seed_demo.py

Builds ~35 grievances from several faculty across every category, spread over the
last six weeks, in every workflow state — enough for the dashboard, Pulse, Gaps
and Analytics to look meaningful. Includes the MVP recurring "Room 204 projector"
scenario and a Block B electrical gap.
"""
from __future__ import annotations

import random
import time

from db import evidence, grievances, recurring, timeline, users
from services import grievance_service as gs
from services import intelligence_service as si

_DAY = 86400.0
_FAC = ["prof.rao", "dr.iyer", "prof.khan", "prof.sharma"]

# (description, location_type, block, floor, room/subzone, days-ago, target-status, priority)
_ITEMS = [
    ("The projector in Room 204 will not switch on again", "academics_block", "Block B", "2nd Floor", "204", 3, "verified", "high"),
    ("Projector 204 is completely dead, no signal to the screen", "academics_block", "Block B", "2nd Floor", "204", 2, "reported", "high"),
    ("Room 204 projector not working - third time this month", "academics_block", "Block B", "2nd Floor", "204", 1, "reported", "high"),
    ("The tube light keeps flickering in this classroom", "academics_block", "Block B", "1st Floor", "101", 12, "assigned", "medium"),
    ("Switchboard is sparking near the entrance of this room", "academics_block", "Block B", "1st Floor", "105", 9, "in_progress", "high"),
    ("Ceiling fan is not working at all in this room", "academics_block", "Block B", "Ground Floor", "108", 20, "resolved", "medium"),
    ("Half the tube lights in this room are not working", "academics_block", "Block B", "3rd Floor", "302", 5, "verified", "medium"),
    ("Power socket near the podium has no output", "academics_block", "Block B", "2nd Floor", "210", 15, "closed", "low"),
    ("Water is leaking from the pipe under the basin in the hostel washroom", "hostels", None, None, None, 25, "closed", "medium"),
    ("The washroom tap on this floor will not stop running", "hostels", None, None, None, 8, "assigned", "medium"),
    ("Drain in the common bathroom is completely blocked", "hostels", None, None, None, 4, "reported", "high"),
    ("No water supply in the hostel since this morning", "hostels", None, None, None, 2, "verified", "high"),
    ("The AC in the mess hall has stopped cooling completely", "mess_canteen", None, None, None, 18, "assigned", "medium"),
    ("Exhaust fan in the kitchen area is making a loud noise", "mess_canteen", None, None, None, 30, "closed", "low"),
    ("A dining table in the mess is broken and unsafe", "mess_canteen", None, None, None, 6, "in_progress", "medium"),
    ("Wall near the notice board has a large crack", "academics_block", "Block C", "Ground Floor", "12", 22, "resolved", "medium"),
    ("Water seepage on the ceiling of this classroom after rain", "academics_block", "Block C", "1st Floor", "118", 14, "assigned", "high"),
    ("Broken window pane in the corridor of Block C", "academics_block", "Block C", "2nd Floor", "205", 10, "verified", "medium"),
    ("The classroom door lock is jammed and will not open", "academics_block", "Block C", "Ground Floor", "9", 7, "in_progress", "medium"),
    ("Several floor tiles are cracked and lifting near the lab", "academics_block", "Block C", "1st Floor", "121", 33, "closed", "low"),
    ("Wifi has been down in this block for two days", "academics_block", "Block A", "2nd Floor", "301", 11, "assigned", "high"),
    ("The classroom computer will not boot up", "academics_block", "Block A", "1st Floor", "110", 16, "resolved", "medium"),
    ("Smart board in this room shows no signal over HDMI", "academics_block", "Block A", "3rd Floor", "315", 5, "reported", "medium"),
    ("Network port in the staff room is not connecting", "academics_block", "Block A", "Ground Floor", "3", 28, "closed", "low"),
    ("The printer in the department office is out of order", "academics_block", "Block A", "1st Floor", "112", 9, "verified", "low"),
    ("Lift in Block A has been out of service since morning", "academics_block", "Block A", "Ground Floor", None, 3, "in_progress", "high"),
    ("Water cooler on this floor is not cooling", "academics_block", "Block A", "2nd Floor", None, 13, "assigned", "low"),
    ("Corridor lights on the playground side stay off at night", "outer_area", None, None, "Common/Electrical", 17, "assigned", "medium"),
    ("The security cabin light near the main gate is broken", "outer_area", None, None, "Security", 6, "verified", "medium"),
    ("Sewage is overflowing near the drainage line behind the mess", "outer_area", None, None, "Drainage", 4, "in_progress", "high"),
    ("Sprinklers on the front lawn are stuck on and flooding the path", "outer_area", None, None, "Lawn Area", 21, "closed", "low"),
    ("A section of the boundary fence near the sports complex is damaged", "playground", None, None, None, 26, "resolved", "medium"),
    ("Floodlights on the playground are not switching on", "playground", None, None, None, 9, "assigned", "medium"),
    ("The generator did not switch on during the last power cut", "academics_block", "Block B", "Ground Floor", None, 12, "verified", "high"),
]


def _flat_label(ltype, sub):
    names = {"hostels": "Hostels", "mess_canteen": "Mess / Canteen", "playground": "Playground"}
    if ltype == "outer_area":
        return f"Outer Area - {sub}" if sub else "Outer Area"
    return names.get(ltype, ltype)


def _submit(uname, desc, ltype, block, floor, room, sub, priority):
    u = users.get_by_username(uname)
    if ltype == "academics_block":
        parts = ["Academics Block", block, floor] + ([f"Room {room}"] if room else [])
        label = " > ".join([p for p in parts if p])
    else:
        label = _flat_label(ltype, sub)
    return gs.submit(dict(
        reporter_id=u["id"], description=desc, location_type=ltype, block_no=block,
        floor=floor, room=room, sub_zone=sub, location_label=label,
        photo_b64="aGVsbG8=", photo_mime="image/jpeg", severity=priority))


def _advance(code, target):
    order = ["reported", "verified", "assigned", "in_progress", "resolved",
             "admin_verified", "closed"]
    g = grievances.get_by_code(code)
    units = {"academics_block": "Class", "hostels": "Housekeeping", "mess_canteen": "Mess",
             "playground": "Landscaping", "outer_area": "Infrastructure"}
    while order.index(g["status"]) < order.index(target):
        cur = g["status"]
        if cur == "reported":
            gs.transition(g["id"], "verified", actor="admin", actor_role="admin")
        elif cur == "verified":
            gs.assign(g["id"], unit=units.get(g["location_type"], "Infrastructure"),
                      assignee="Maintenance team", actor="admin")
        elif cur == "assigned":
            gs.transition(g["id"], "in_progress", actor="admin", actor_role="admin")
        elif cur == "in_progress":
            gs.add_resolution_evidence(g["id"], kind="resolution_after", image_b64="aGk=",
                                       mime="image/png", note="Repaired and tested.", actor="admin")
            gs.transition(g["id"], "resolved", actor="admin", actor_role="admin")
        elif cur == "resolved":
            gs.transition(g["id"], "admin_verified", actor="admin", actor_role="admin")
        elif cur == "admin_verified":
            gs.transition(g["id"], "closed", actor="admin", actor_role="admin")
        g = grievances.get_by_code(code)


def _counts() -> dict:
    return {"grievances": len(grievances.list_query(limit=100000)),
            "recurring_groups": len(si.recurring.list_active()),
            "gaps": len(si.gaps())}


def build() -> dict:
    if grievances.list_query(limit=1):
        return _counts()

    random.seed(7)
    now = time.time()
    for i, (desc, lt, blk, flr, rm, days_ago, target, pri) in enumerate(_ITEMS):
        uname = _FAC[i % len(_FAC)]
        room = rm if lt == "academics_block" else None
        sub = rm if lt == "outer_area" else None
        try:
            out = _submit(uname, desc, lt, blk, flr, room, sub, pri)
        except gs.SubmissionError:
            continue
        g = grievances.get_by_code(out["code"])
        created = now - days_ago * _DAY - random.uniform(0, _DAY)
        grievances.update(g["id"], created_at=created)
        if target != "reported":
            _advance(out["code"], target)
        g = grievances.get_by_code(out["code"])
        if g.get("resolved_at"):   # realistic: resolved 1-5 days after it was reported
            grievances.update(g["id"], resolved_at=created + random.uniform(1, 5) * _DAY)
        if g.get("assigned_at"):
            grievances.update(g["id"], assigned_at=created + random.uniform(0.2, 2) * _DAY)
        # make a few assigned/in-progress ones overdue
        g = grievances.get_by_code(out["code"])
        if g["status"] in ("assigned", "in_progress") and days_ago > 10:
            grievances.update(g["id"], due_at=now - random.uniform(1, 4) * _DAY)

    return _counts()


if __name__ == "__main__":
    from db import pool, seeds
    pool.init_db()
    seeds.run()
    print(build())
