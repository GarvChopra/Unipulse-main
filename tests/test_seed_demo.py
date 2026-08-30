from scripts import seed_demo
from services import intelligence_service as si


def test_build_creates_recurring_and_gap(memstore):
    from db import seeds
    seeds.run()
    out = seed_demo.build()
    assert out["grievances"] >= 10
    assert out["recurring_groups"] >= 1
    assert out["gaps"] >= 1
    groups = si.recurring.list_active()
    assert any("204" in g["title"] for g in groups)


def test_build_is_idempotent(memstore):
    from db import seeds
    seeds.run()
    first = seed_demo.build()
    second = seed_demo.build()
    assert second == first
