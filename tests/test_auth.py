import pytest

from services import auth_service


def test_pin_hash_roundtrip():
    h = auth_service.hash_pin("1234")
    assert h != "1234"
    assert auth_service.verify_pin("1234", h)
    assert not auth_service.verify_pin("0000", h)


def test_access_token_roundtrip():
    tok = auth_service.create_access_token(
        {"username": "admin", "display_name": "Sir", "role": "admin", "department": None}
    )
    payload = auth_service.decode_access_token(tok)
    assert payload["sub"] == "admin"
    assert payload["role"] == "admin"


def test_decode_rejects_garbage():
    with pytest.raises(auth_service.AuthError):
        auth_service.decode_access_token("not-a-token")


def test_rate_limit_trips_after_five():
    key = "u@1.2.3.4"
    assert all(auth_service.check_rate_limit(key) for _ in range(5))
    assert auth_service.check_rate_limit(key) is False
