import time

from services.classification_service import priority_score


def _g(**kw):
    base = dict(severity="medium", category=None, status="reported",
                created_at=time.time(), location_type="hostels", sub_zone=None)
    base.update(kw)
    return base


def test_high_severity_electric_academics_scores_high():
    g = _g(severity="high", category="Electric", location_type="academics_block")
    # 45 (high) + 15 (electric) + 8 (academics) = 68
    assert priority_score(g) == 68


def test_low_floor_score():
    g = _g(severity="low", category="IT / Network", location_type="playground")
    # 10 + 3 + 0 = 13
    assert priority_score(g) == 13


def test_recurrence_adds_capped_boost():
    g = _g(severity="low", category="IT / Network", location_type="playground")
    grp = {"status": "active", "report_count": 30}
    # 13 + min(20, 2*30) = 33
    assert priority_score(g, recurring_group=grp) == 33


def test_age_boost_capped_and_clamped_to_100():
    old = time.time() - 40 * 86400
    g = _g(severity="high", category="Electric", status="verified",
           location_type="academics_block", created_at=old)
    # 45 + 15 + 8 + min(15, 40) = 83
    assert priority_score(g) == 83


def test_score_never_exceeds_100():
    old = time.time() - 999 * 86400
    g = _g(severity="high", category="Civil", location_type="academics_block", created_at=old)
    grp = {"status": "active", "report_count": 99}
    assert priority_score(g, recurring_group=grp) == 100


def test_affects_academics_adds_ten():
    g = _g(severity="low", category="IT / Network", location_type="playground",
           affects_academics=True)
    assert priority_score(g) == 23   # 10 + 3 + 0 + 10
