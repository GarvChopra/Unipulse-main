import pytest

from db import evidence, grievances, users
from services import grievance_service as gs
from services.auth_service import hash_pin


def _in_progress(memstore):
    u = users.create("f", "F", "reporter", hash_pin("1"))
    g = grievances.insert(reporter_id=u["id"], reporter_name="F", title="t",
                          description="the tubelight is not working here",
                          location_type="hostels", location_label="Hostels",
                          category="Electric", severity="medium", status="reported",
                          priority_score=10)
    gs.transition(g["id"], "verified", actor="admin", actor_role="admin")
    gs.assign(g["id"], unit="Infrastructure", assignee="t", actor="admin")
    gs.transition(g["id"], "in_progress", actor="admin", actor_role="admin")
    return g


def test_resolve_blocked_without_evidence(memstore):
    g = _in_progress(memstore)
    with pytest.raises(gs.WorkflowError) as ei:
        gs.transition(g["id"], "resolved", actor="admin", actor_role="admin")
    assert "after" in ei.value.message.lower()


def test_resolve_blocked_with_evidence_but_no_note(memstore):
    g = _in_progress(memstore)
    evidence.add(g["id"], "resolution_after", image_url="data:image/png;base64,aGk=",
                 note="", uploaded_by="admin")
    with pytest.raises(gs.WorkflowError):
        gs.transition(g["id"], "resolved", actor="admin", actor_role="admin")


def test_resolve_allowed_with_evidence_and_note(memstore):
    g = _in_progress(memstore)
    gs.add_resolution_evidence(g["id"], kind="resolution_after",
                               image_b64="aGk=", mime="image/png",
                               note="Replaced the tubelight and the choke", actor="admin")
    out = gs.transition(g["id"], "resolved", actor="admin", actor_role="admin")
    assert out["status"] == "resolved"
