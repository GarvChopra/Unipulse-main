def test_offline_page_no_login(client):
    r = client.get("/offline")
    assert r.status_code == 200
    assert b"offline" in r.data.lower()


def test_service_worker_has_offline_fallback(client):
    sw = client.get("/static/service-worker.js").data.decode()
    assert "/offline" in sw
    assert 'req.mode === "navigate"' in sw


def test_base_page_has_install_button(client):
    client.post("/login", data={"username": "prof.rao", "pin": "1234"})
    r = client.get("/")
    assert b"beforeinstallprompt" in r.data
    assert b'id="pwa-install"' in r.data
