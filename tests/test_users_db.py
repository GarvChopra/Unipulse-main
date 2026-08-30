import pytest

from db import users
from services.auth_service import hash_pin, verify_pin


def test_create_and_fetch(memstore):
    u = users.create("prof.rao", "Prof Rao", "reporter", hash_pin("1111"), department="CSE")
    assert u["id"] > 0
    assert users.get_by_username("prof.rao")["display_name"] == "Prof Rao"
    assert users.get_by_id(u["id"])["role"] == "reporter"


def test_duplicate_username_rejected(memstore):
    users.create("dup", "One", "reporter", hash_pin("1"))
    with pytest.raises(ValueError):
        users.create("dup", "Two", "reporter", hash_pin("2"))


def test_list_by_role(memstore):
    users.create("a1", "A1", "admin", hash_pin("1"))
    users.create("r1", "R1", "reporter", hash_pin("1"))
    assert {u["username"] for u in users.list_all(role="reporter")} == {"r1"}


def test_set_active_and_pin(memstore):
    u = users.create("x", "X", "reporter", hash_pin("1"))
    users.set_active(u["id"], False)
    assert users.get_by_id(u["id"])["is_active"] is False
    users.set_pin(u["id"], hash_pin("2"))
    assert verify_pin("2", users.get_by_id(u["id"])["pin_hash"])
