def test_app_boots_in_memory(app):
    from db import pool
    assert pool.STATE["mode"] == "memory"


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.get_json()["db"] == "memory"


def test_login_page_renders(client):
    r = client.get("/login")
    assert r.status_code == 200
    assert b"UniPulse" in r.data
