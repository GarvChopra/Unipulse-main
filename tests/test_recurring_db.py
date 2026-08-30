from db import recurring


def test_create_find_bump(memstore):
    assert recurring.find_active("Hostels", "Plumbing") is None
    grp = recurring.create("Hostels", "Plumbing", "Hostels - Plumbing", 10, 100.0)
    assert grp["status"] == "active"
    assert recurring.find_active("Hostels", "Plumbing")["id"] == grp["id"]
    grp = recurring.bump(grp["id"], last_ts=200.0, add_reporter=True)
    grp = recurring.bump(grp["id"], last_ts=300.0, add_reporter=False)
    assert grp["report_count"] == 2
    assert grp["reporter_count"] == 1
    assert grp["last_reported_at"] == 300.0


def test_resolved_group_not_found_as_active(memstore):
    grp = recurring.create("Playground", "Civil", "t", 1, 1.0)
    recurring.set_status(grp["id"], "resolved")
    assert recurring.find_active("Playground", "Civil") is None
