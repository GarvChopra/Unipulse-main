import pytest

from db import evidence, grievances, recurring, timeline, users
from services import grievance_service as gs
from services.auth_service import hash_pin


def _sub(reporter_id, **kw):
    base = dict(
        reporter_id=reporter_id,
        description="The ceiling fan in this room has completely stopped working",
        location_type="academics_block", block_no="Block B", floor="2nd Floor",
        room="204", sub_zone=None,
        location_label="Academics Block > Block B > 2nd Floor > Room 204",
        photo_b64="aGVsbG8gd29ybGQ=", photo_mime="image/jpeg",
    )
    base.update(kw)
    return base


def test_happy_path_creates_grievance_evidence_timeline(memstore):
    u = users.create("f1", "Faculty One", "reporter", hash_pin("1"))
    out = gs.submit(_sub(u["id"]))
    assert out["code"].startswith("GLB-CAMP-")
    assert out["recurring"] is None
    g = grievances.get_by_code(out["code"])
    assert g["status"] == "reported"
    assert g["category"] in ("Electric", "Power")
    assert g["priority_score"] > 0
    assert g["primary_photo_url"] == f"/photo/{evidence.list_for(g['id'])[0]['id']}"
    assert [e["kind"] for e in evidence.list_for(g["id"])] == ["report"]
    assert [e["event_type"] for e in timeline.list_for(g["id"])] == ["created"]


def test_validation_error_raises(memstore):
    u = users.create("f2", "F2", "reporter", hash_pin("1"))
    with pytest.raises(gs.SubmissionError) as ei:
        gs.submit(_sub(u["id"], description="nope"))
    assert ei.value.errors


def test_same_reporter_24h_duplicate_raises(memstore):
    u = users.create("f3", "F3", "reporter", hash_pin("1"))
    gs.submit(_sub(u["id"], description="Water leaking from the pipe under the basin"))
    with pytest.raises(gs.SubmissionError):
        gs.submit(_sub(u["id"], description="Water leaking from the pipe under the basin"))


def test_second_reporter_forms_recurring_group(memstore):
    u1 = users.create("a", "A", "reporter", hash_pin("1"))
    u2 = users.create("b", "B", "reporter", hash_pin("1"))
    d = "Water is leaking from the pipe under the basin in this washroom"
    label = "Academics Block > Block B > 2nd Floor > Room 204"
    gs.submit(_sub(u1["id"], description=d, location_label=label))
    out2 = gs.submit(_sub(u2["id"], description=d, location_label=label))
    assert out2["recurring"] is not None
    grp = recurring.get(out2["recurring"]["group_id"])
    assert grp["report_count"] == 2
    assert grp["reporter_count"] == 2
    codes = [x for x in grievances.list_query() if x["recurring_group_id"] == grp["id"]]
    assert len(codes) == 2
    for g in codes:
        types = [e["event_type"] for e in timeline.list_for(g["id"])]
        assert "merged_recurring" in types


def test_precomputed_ai_is_used(memstore):
    u = users.create("f4", "F4", "reporter", hash_pin("1"))
    out = gs.submit(_sub(u["id"], ai={"category": "IT / Network", "severity": "high",
                                      "ai_summary": "Projector dead", "confidence": 90,
                                      "spam_flag": False}))
    assert grievances.get_by_code(out["code"])["category"] == "IT / Network"
    assert grievances.get_by_code(out["code"])["ai_summary"] == "Projector dead"


def test_spam_flag_persisted(memstore):
    u = users.create("sp", "SP", "reporter", hash_pin("1"))
    out = gs.submit(_sub(u["id"], description="asdf asdf test test 12345"))
    assert grievances.get_by_code(out["code"])["spam_flag"] is True


def test_form_severity_overrides_ai(memstore):
    u = users.create("fs", "FS", "reporter", hash_pin("1"))
    out = gs.submit(_sub(u["id"], description="minor cosmetic paint chip on the wall",
                         severity="high"))
    assert grievances.get_by_code(out["code"])["severity"] == "high"


def test_affects_academics_bumps_priority_and_persists(memstore):
    u = users.create("fa", "FA", "reporter", hash_pin("1"))
    a = gs.submit(_sub(u["id"], severity="low"))
    b_u = users.create("fb", "FB", "reporter", hash_pin("1"))
    b = gs.submit(_sub(b_u["id"], severity="low", affects_academics=True,
                       location_label="Academics Block > Block C > 1st Floor > Room 9"))
    ga = grievances.get_by_code(a["code"]); gb = grievances.get_by_code(b["code"])
    assert gb["affects_academics"] is True
    assert gb["priority_score"] == ga["priority_score"] + 10
