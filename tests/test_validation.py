from services.validation_service import validate_submission

_OK = dict(description="The ceiling fan in this room has stopped working",
           location_type="academics_block",
           location_label="Academics Block > Block B > 2nd Floor > Room 204",
           photo_b64="aGVsbG8=")


def test_valid_submission_has_no_errors():
    assert validate_submission(dict(_OK)) == []


def test_description_too_short():
    s = dict(_OK, description="broken")
    assert any("10 characters" in e for e in validate_submission(s))


def test_missing_photo():
    s = dict(_OK); s.pop("photo_b64")
    assert any("photo" in e.lower() for e in validate_submission(s))


def test_bad_location_type():
    s = dict(_OK, location_type="rooftop")
    assert any("location" in e.lower() for e in validate_submission(s))


def test_missing_location_label():
    s = dict(_OK, location_label="")
    assert validate_submission(s) != []


def test_bad_category_rejected():
    s = dict(_OK, category="Wifi")
    assert any("category" in e.lower() for e in validate_submission(s))
