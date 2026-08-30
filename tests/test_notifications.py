from services import notification_service as ns


def test_no_op_without_api_key(monkeypatch):
    monkeypatch.setattr("config.Config.RESEND_API_KEY", "", raising=False)
    r = ns.notify_status_change({"code": "GLB-CAMP-00001"}, "verified", "prof@glbitm.ac.in")
    assert r == {"sent": False, "reason": "not_configured"}


def test_no_op_without_reporter_contact(monkeypatch):
    monkeypatch.setattr("config.Config.RESEND_API_KEY", "test-key", raising=False)
    r = ns.notify_status_change({"code": "GLB-CAMP-00001"}, "verified", None)
    assert r["sent"] is False


def test_status_change_delivers(monkeypatch):
    sent = {}
    monkeypatch.setattr("config.Config.RESEND_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(ns, "_deliver",
                        lambda to, subject, html: sent.update(to=to, subject=subject, html=html)
                        or {"sent": True, "reason": "ok"})
    r = ns.notify_status_change({"code": "GLB-CAMP-00042", "location_label": "Hostels"},
                                "resolved", "prof@glbitm.ac.in")
    assert r["sent"] is True
    assert sent["to"] == "prof@glbitm.ac.in"
    assert "GLB-CAMP-00042" in sent["subject"]
    assert "resolved" in sent["html"].lower()


def test_high_priority_alert_to_admin(monkeypatch):
    sent = {}
    monkeypatch.setattr("config.Config.RESEND_API_KEY", "test-key", raising=False)
    monkeypatch.setattr("config.Config.ADMIN_ALERT_EMAIL", "sir@glbitm.ac.in", raising=False)
    monkeypatch.setattr(ns, "_deliver",
                        lambda to, subject, html: sent.update(to=to) or {"sent": True, "reason": "ok"})
    r = ns.notify_new_high_priority({"code": "GLB-CAMP-00007", "category": "Electric",
                                     "priority_score": 80, "location_label": "Block B"})
    assert r["sent"] is True
    assert sent["to"] == "sir@glbitm.ac.in"


def test_deliver_failure_is_swallowed(monkeypatch):
    monkeypatch.setattr("config.Config.RESEND_API_KEY", "test-key", raising=False)

    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(ns, "_deliver", boom)
    r = ns.notify_status_change({"code": "x", "location_label": "y"}, "verified", "a@b.com")
    assert r["sent"] is False
    assert "network down" in r["reason"]


def test_pipeline_triggers_alert_and_status_email(monkeypatch, memstore):
    from db import users
    from services import grievance_service as gs
    from services.auth_service import hash_pin

    calls = []
    monkeypatch.setattr("services.notification_service.notify_new_high_priority",
                        lambda g: calls.append(("alert", g["code"])) or {"sent": True})
    monkeypatch.setattr("services.notification_service.notify_status_change",
                        lambda g, s, c: calls.append(("status", s)) or {"sent": True})

    u = users.create("prof.x", "Prof X", "reporter", hash_pin("1"),
                     contact="profx@glbitm.ac.in")
    out = gs.submit({
        "reporter_id": u["id"],
        "description": "Exposed live wire sparking near the door, very dangerous",
        "location_type": "academics_block", "block_no": "Block B", "floor": "2nd Floor",
        "room": "204", "location_label": "Academics Block > Block B > 2nd Floor > Room 204",
        "photo_b64": "aGVsbG8=", "photo_mime": "image/jpeg",
    })
    assert ("alert", out["code"]) in calls
    g = gs.grievances.get_by_code(out["code"])
    gs.transition(g["id"], "verified", actor="admin", actor_role="admin")
    assert ("status", "verified") in calls
