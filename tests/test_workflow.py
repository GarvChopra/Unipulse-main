import pytest

from db import evidence, grievances, timeline, users
from services import grievance_service as gs
from services.auth_service import hash_pin


def _grievance(memstore, category="Electric", status="reported"):
    u = users.create("f", "Faculty", "reporter", hash_pin("1"))
    g = grievances.insert(reporter_id=u["id"], reporter_name="Faculty", title="t",
                          description="the ceiling fan is not working in this room",
                          location_type="academics_block", block_no="Block B",
                          location_label="Academics Block > Block B > 2nd Floor > Room 204",
                          category=category, severity="medium", status=status,
                          priority_score=10)
    return g


def test_verify_then_assign_sets_sla_due(memstore):
    g = _grievance(memstore, category="Electric")
    gs.transition(g["id"], "verified", actor="admin", actor_role="admin")
    out = gs.assign(g["id"], unit="Infrastructure", assignee="Ravi (electrician)", actor="admin")
    assert out["status"] == "assigned"
    assert out["responsible_unit"] == "Infrastructure"
    assert abs(out["due_at"] - (out["assigned_at"] + 24 * 3600)) < 5
    events = [e["event_type"] for e in timeline.list_for(g["id"])]
    assert "status_change" in events and "assigned" in events


def test_illegal_transition_rejected(memstore):
    g = _grievance(memstore)
    with pytest.raises(gs.WorkflowError):
        gs.transition(g["id"], "closed", actor="admin", actor_role="admin")


def test_assign_requires_verified(memstore):
    g = _grievance(memstore, status="reported")
    with pytest.raises(gs.WorkflowError):
        gs.assign(g["id"], unit="Infrastructure", assignee="x", actor="admin")


def test_correct_category_recomputes_priority(memstore):
    g = _grievance(memstore, category="IT / Network")
    before = grievances.get_by_id(g["id"])["priority_score"]
    gs.correct_category(g["id"], category="Electric", actor="admin")
    after = grievances.get_by_id(g["id"])["priority_score"]
    assert after > before
    assert grievances.get_by_id(g["id"])["category_confirmed"] is True


def test_full_lifecycle_to_closed(memstore):
    g = _grievance(memstore)
    gs.transition(g["id"], "verified", actor="admin", actor_role="admin")
    gs.assign(g["id"], unit="Infrastructure", assignee="team", actor="admin")
    gs.transition(g["id"], "in_progress", actor="admin", actor_role="admin")
    evidence.add(g["id"], "resolution_after", image_url="data:image/png;base64,aGk=",
                 note="Replaced the fan capacitor", uploaded_by="admin")
    gs.transition(g["id"], "resolved", actor="admin", actor_role="admin")
    assert grievances.get_by_id(g["id"])["resolved_at"] is not None
    gs.transition(g["id"], "admin_verified", actor="admin", actor_role="admin")
    gs.transition(g["id"], "closed", actor="admin", actor_role="admin")
    assert grievances.get_by_id(g["id"])["closed_at"] is not None


def test_reopen_clears_resolved_at(memstore):
    g = _grievance(memstore)
    gs.transition(g["id"], "verified", actor="admin", actor_role="admin")
    gs.assign(g["id"], unit="Infrastructure", assignee="t", actor="admin")
    gs.transition(g["id"], "in_progress", actor="admin", actor_role="admin")
    evidence.add(g["id"], "resolution_after", image_url="data:image/png;base64,aGk=",
                 note="fixed", uploaded_by="admin")
    gs.transition(g["id"], "resolved", actor="admin", actor_role="admin")
    gs.reopen(g["id"], actor="admin", note="Problem came back")
    row = grievances.get_by_id(g["id"])
    assert row["status"] == "in_progress"
    assert row["resolved_at"] is None
    assert "reopened" in [e["event_type"] for e in timeline.list_for(g["id"])]
