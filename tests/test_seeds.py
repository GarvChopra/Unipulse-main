from db import notices, seeds, users


def test_seed_creates_admin_and_faculty(memstore):
    seeds.run()
    admin = users.get_by_username("admin")
    assert admin and admin["role"] == "admin"
    assert len(users.list_all(role="reporter")) >= 4


def test_seed_is_idempotent(memstore):
    seeds.run()
    seeds.run()
    assert len(users.list_all()) == 1 + len(seeds.DEMO_FACULTY)
    assert len(notices.list_published()) == 2


def test_admin_pin_is_0000(memstore):
    seeds.run()
    from services.auth_service import verify_pin
    assert verify_pin("0000", users.get_by_username("admin")["pin_hash"])
