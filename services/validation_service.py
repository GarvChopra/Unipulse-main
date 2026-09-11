"""Inbound grievance submission validation. Pure - no I/O."""
from __future__ import annotations

from domain.constants import CATEGORIES, LOCATION_TYPES

_VALID_TYPES = {t["key"] for t in LOCATION_TYPES}
_DESC_MIN, _DESC_MAX = 10, 300


def validate_submission(sub: dict) -> list[str]:
    errors: list[str] = []

    desc = (sub.get("description") or "").strip()
    if len(desc) < _DESC_MIN:
        errors.append(f"Description must be at least {_DESC_MIN} characters.")
    elif len(desc) > _DESC_MAX:
        errors.append(f"Description must be {_DESC_MAX} characters or fewer.")

    if (sub.get("location_type") or "") not in _VALID_TYPES:
        errors.append("Pick a valid campus location type.")
    if not (sub.get("location_label") or "").strip():
        errors.append("Location is required.")

    # A photo is encouraged but optional — the reporter can fill in the form
    # without one (the wizard offers a "No photo?" skip on the photo step).

    cat = sub.get("category")
    if cat and cat not in CATEGORIES:
        errors.append(f"Unknown category {cat!r}.")

    return errors
