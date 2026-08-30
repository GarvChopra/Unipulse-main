from domain import constants as c


def test_six_categories_in_order():
    assert c.CATEGORIES == ["Electric", "Plumbing", "Civil", "Mechanical", "Power", "IT / Network"]


def test_seven_statuses_in_order():
    assert c.STATUSES == ["reported", "verified", "assigned", "in_progress",
                          "resolved", "admin_verified", "closed"]


def test_forward_transitions_are_single_step():
    for i, s in enumerate(c.STATUSES[:-1]):
        assert c.STATUSES[i + 1] in c.STATUS_TRANSITIONS[s]
    assert c.STATUS_TRANSITIONS["closed"] == []
    assert "in_progress" in c.STATUS_TRANSITIONS["resolved"]        # reopen
    assert "in_progress" in c.STATUS_TRANSITIONS["admin_verified"]  # reopen


def test_responsible_units():
    assert c.RESPONSIBLE_UNITS["College"] == ["Infrastructure", "Sanitation", "Housekeeping",
                                              "Landscaping", "Mess", "Parking"]
    assert c.RESPONSIBLE_UNITS["Academics"] == ["Class", "Lab"]
    assert set(c.RESPONSIBLE_UNITS_FLAT) == {"Infrastructure", "Sanitation", "Housekeeping",
                                             "Landscaping", "Mess", "Parking", "Class", "Lab"}


def test_sla_hours_cover_every_category():
    assert set(c.SLA_HOURS) == set(c.CATEGORIES)
    assert all(isinstance(v, int) and v > 0 for v in c.SLA_HOURS.values())


def test_glb_identity():
    assert c.GLB["name"] == "GL Bajaj Institute of Technology and Management"
    assert c.CODE_PREFIX == "GLB-CAMP-"
