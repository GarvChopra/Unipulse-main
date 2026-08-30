import time

from db import grievances, recurring, users
from services import intelligence_service as si
from services.auth_service import hash_pin


def _g(memstore, **kw):
    u = kw.pop("_u", None) or users.create(f"u{time.time_ns()}", "U", "reporter", hash_pin("1"))
    base = dict(reporter_id=u["id"], reporter_name="U", title="t",
                description="a broken item is here now", location_type="hostels",
                location_label="Hostels", category="Electric", severity="medium",
                status="reported", priority_score=10)
    base.update(kw)
    return grievances.insert(**base)


# ── KPIs ───────────────────────────────────────────────────────────────────

def test_kpis_counts(memstore):
    _g(memstore, status="reported")
    _g(memstore, status="assigned")
    _g(memstore, status="resolved")
    g = _g(memstore, status="in_progress")
    grievances.update(g["id"], due_at=time.time() - 3600)
    k = si.kpis()
    assert k["total"] == 4
    assert k["open"] == 1
    assert k["in_progress"] == 2
    assert k["resolved"] == 1
    assert k["sla_breaches"] == 1


def test_recurring_kpi(memstore):
    recurring.create("Hostels", "Electric", "t", 1, time.time())
    assert si.kpis()["recurring"] == 1


def test_overdue_sorted_worst_first(memstore):
    a = _g(memstore, status="assigned"); grievances.update(a["id"], due_at=time.time() - 100)
    b = _g(memstore, status="assigned"); grievances.update(b["id"], due_at=time.time() - 9999)
    ov = si.overdue()
    assert [x["id"] for x in ov] == [b["id"], a["id"]]


# ── Pulse ──────────────────────────────────────────────────────────────────

def test_pulse_all_healthy_when_empty(memstore):
    for d in si.pulse():
        assert d["score"] == 100
        assert d["open_count"] == 0


def test_pulse_electrical_drops_with_open_high_severity(memstore):
    for i in range(3):
        _g(memstore, category="Electric", severity="high", status="reported")
    dom = {d["key"]: d for d in si.pulse()}["electrical"]
    assert dom["open_count"] == 3
    assert dom["high_open"] == 3
    assert dom["score"] == 70
    assert dom["factors"]


def test_pulse_domain_matches_by_location_type(memstore):
    _g(memstore, category="Plumbing", location_type="academics_block", status="reported")
    classrooms = {d["key"]: d for d in si.pulse()}["classrooms"]
    assert classrooms["open_count"] == 1


# ── Gaps ───────────────────────────────────────────────────────────────────

def test_gaps_surfaces_bucket_over_threshold(memstore):
    for i in range(4):
        _g(memstore, category="Electric", location_type="academics_block", block_no="Block B",
           location_label="Academics Block > Block B > 1st Floor > Room 1", status="reported")
    _g(memstore, category="Electric", location_type="academics_block", block_no="Block C",
       status="reported")
    gaps = si.gaps()
    assert len(gaps) == 1
    assert gaps[0]["location"] == "Block B"
    assert gaps[0]["category"] == "Electric"
    assert gaps[0]["count"] == 4
    assert gaps[0]["recommended_action"]
