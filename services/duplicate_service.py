"""Campus recurring / duplicate detection (replaces AreaPulse geo-radius)."""
from __future__ import annotations

import time

from db import grievances
from domain.constants import RECURRING_WINDOW_DAYS

_DAY = 86400.0


def find_recurring(location_label: str, category, reporter_id, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    if not category:
        return {"same_reporter_recent": False, "candidates": [], "match": False}

    since = now - RECURRING_WINDOW_DAYS * _DAY
    candidates = grievances.find_recurring_candidates(location_label, category, since)

    same_reporter_recent = any(
        c.get("reporter_id") == reporter_id and (c.get("created_at") or 0) >= now - _DAY
        for c in candidates
    )
    return {
        "same_reporter_recent": same_reporter_recent,
        "candidates": candidates,
        "match": bool(candidates) and not same_reporter_recent,
    }
