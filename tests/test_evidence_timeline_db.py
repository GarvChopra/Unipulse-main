from db import audit, evidence, grievances, timeline, users
from services.auth_service import hash_pin


def _g():
    u = users.create("f", "F", "reporter", hash_pin("1"))
    return grievances.insert(reporter_id=u["id"], reporter_name="F", title="t",
                             description="a description here", location_type="hostels",
                             location_label="Hostels")


def test_evidence_roundtrip(memstore):
    g = _g()
    evidence.add(g["id"], "report", image_url="u1", uploaded_by="F")
    assert not evidence.has_kind(g["id"], "resolution_after")
    evidence.add(g["id"], "resolution_after", image_url="u2", note="fixed", uploaded_by="admin")
    assert evidence.has_kind(g["id"], "resolution_after")
    kinds = [e["kind"] for e in evidence.list_for(g["id"])]
    assert kinds == ["report", "resolution_after"]


def test_timeline_ordering(memstore):
    g = _g()
    timeline.add(g["id"], "created", actor="F", actor_role="reporter")
    timeline.add(g["id"], "status_change", from_value="reported", to_value="verified",
                 actor="admin", actor_role="admin")
    evs = timeline.list_for(g["id"])
    assert [e["event_type"] for e in evs] == ["created", "status_change"]
    assert evs[1]["to_value"] == "verified"


def test_audit_recent_newest_first(memstore):
    audit.add("admin", "user.create", target_type="user", target_id="7")
    audit.add("admin", "notice.publish", target_type="notice", target_id="2")
    recent = audit.list_recent()
    assert recent[0]["action"] == "notice.publish"
