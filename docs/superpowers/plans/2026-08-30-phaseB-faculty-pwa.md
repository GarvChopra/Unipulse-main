# UniPulse — Phase B (Faculty PWA) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Faculty can log in on a phone, report a campus infrastructure problem
(photo → location → description → AI summary → submit), get a `GLB-CAMP-#####` id,
and track their reports + status timeline. Installable PWA.

**Architecture:** New `faculty` Flask blueprint on the Phase-0/A app factory. Submit
goes through `grievance_service.submit()`: validate → same-reporter dup guard →
classify (Groq w/ keyword fallback) → recurring-group detection → insert
`grievances` + `evidence('report')` + `timeline('created')`. Server-rendered Jinja
+ vanilla JS, no build step. Photos stored via the existing `storage_service`
(passthrough data-URI by default) and served through an auth-gated `/photo/<id>`.

**Tech Stack:** Python 3.12, Flask 3, `requests` (Groq REST call — no new dep),
pytest 9. Groq is optional; everything falls back to deterministic keyword logic.

**Spec:** `docs/superpowers/specs/2026-08-30-unipulse-campus-design.md` (§8 pipeline,
§9 priority, §10 intelligence is Phase D, §11 testing). Builds on
`docs/superpowers/plans/2026-08-30-phase0-A-restructure-and-data.md` (done).

## Global Constraints

- Product **UniPulse**; institution **GL Bajaj Institute of Technology and Management** (short **GL Bajaj**). Codes `GLB-CAMP-` + 5 digits.
- Categories (exact, ordered): `Electric, Plumbing, Civil, Mechanical, Power, IT / Network`. Severities: `low, medium, high`.
- Statuses forward-only: `reported → verified → assigned → in_progress → resolved → admin_verified → closed`.
- `RECURRING_WINDOW_DAYS = 14`. Same reporter + same `location_label` + same `category` within **24h** → reject as a true duplicate. Different reporter (or >24h) matching within the window → group.
- Every submission creates its own `grievances` row. Recurring grouping never suppresses a row.
- Roles `reporter`/`admin`. Faculty routes require a logged-in user; a logged-in `admin` hitting `/` is redirected to `/admin`.
- Timestamps epoch floats. No `session`. No new pip deps beyond what `requirements.txt` already lists.
- Tests run in-memory (`conftest.py` pops `DATABASE_URL`); Groq is unavailable in tests (`GROQ_API_KEY` unset) so keyword fallback runs.
- No commits (the user runs git themselves).

---

## File Structure

**Created:**
- `ai/__init__.py`, `ai/engine.py` — Groq REST client + campus prompts
- `services/validation_service.py` — `validate_submission(sub) -> list[str]`
- `services/classification_service.py` — `classify()`, `priority_score()`, keyword fallback
- `services/duplicate_service.py` — recurring detection
- `services/grievance_service.py` — `submit()` pipeline
- `blueprints/faculty/__init__.py` — faculty routes
- `templates/faculty/home.html`, `report.html`, `my_reports.html`, `grievance_detail.html`, `notices.html`
- `static/js/report.js` — the report wizard
- `static/manifest.webmanifest`, `static/service-worker.js`, `static/icons/icon-192.png`, `static/icons/icon-512.png`
- `tests/test_validation.py`, `tests/test_classification.py`, `tests/test_priority.py`, `tests/test_duplicate_service.py`, `tests/test_grievance_pipeline.py`, `tests/test_faculty_routes.py`
- `scripts/make_icons.py` — pure-Python PNG icon generator (run once)

**Modified:**
- `app.py` — register `faculty` blueprint; add `<link rel="manifest">` handled in base template; nothing else
- `templates/base_faculty.html` — real mobile shell + bottom nav + PWA head tags + SW registration
- `config.py` — add `GROQ_MODEL_TEXT`, `GROQ_MODEL_VISION`

---

### Task 1: `services/validation_service.py`

**Files:**
- Create: `services/validation_service.py`
- Test: `tests/test_validation.py`

**Interfaces:**
- Produces: `validate_submission(sub: dict) -> list[str]` — empty list = valid. `sub` keys used: `description, location_type, location_label, photo_b64, category` (category optional).

- [ ] **Step 1: Write `tests/test_validation.py`**

```python
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
```

- [ ] **Step 2: Run — fails.** `pytest tests/test_validation.py -q`

- [ ] **Step 3: Write `services/validation_service.py`**

```python
"""Inbound grievance submission validation. Pure — no I/O."""
from __future__ import annotations

from domain.constants import CATEGORIES, LOCATION_TYPES, SEVERITIES

_VALID_TYPES = {t["key"] for t in LOCATION_TYPES}
_DESC_MIN, _DESC_MAX = 10, 2000


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

    if not (sub.get("photo_b64") or "").strip():
        errors.append("A photo of the problem is required.")

    cat = sub.get("category")
    if cat and cat not in CATEGORIES:
        errors.append(f"Unknown category {cat!r}.")
    sev = sub.get("severity")
    if sev and sev not in SEVERITIES:
        errors.append(f"Unknown severity {sev!r}.")

    return errors
```

- [ ] **Step 4: Run — passes.**

---

### Task 2: `ai/engine.py` — Groq REST client

**Files:**
- Create: `ai/__init__.py` (empty), `ai/engine.py`
- Modify: `config.py`
- Test: none directly (unavailable in tests); exercised via `classification_service` fallback tests.

**Interfaces:**
- Produces:
  - `engine.is_available() -> bool` — `bool(Config.GROQ_API_KEY)`
  - `engine.classify(description: str, photo_b64: str | None = None, photo_mime: str = "image/jpeg") -> dict | None` — returns `{"category": str, "severity": str, "summary": str, "confidence": int, "spam": bool}` on success, `None` on any failure/unavailable. `category` is guaranteed to be one of `CATEGORIES` or the function returns `None`.

- [ ] **Step 1: Add to `config.py`** (after `IMAGEKIT_PRIVATE_KEY`):

```python
    GROQ_MODEL_TEXT   = os.environ.get("GROQ_MODEL_TEXT", "llama-3.3-70b-versatile").strip()
    GROQ_MODEL_VISION = os.environ.get("GROQ_MODEL_VISION", "meta-llama/llama-4-scout-17b-16e-instruct").strip()
```

- [ ] **Step 2: Write `ai/__init__.py`** (empty file)

- [ ] **Step 3: Write `ai/engine.py`**

```python
"""Groq classification for campus grievances. Optional — degrades to None."""
from __future__ import annotations

import json

import requests

from config import Config
from domain.constants import CATEGORIES, GLB, SEVERITIES

_URL = "https://api.groq.com/openai/v1/chat/completions"
_TIMEOUT = 20

_SYSTEM = (
    f"You triage infrastructure grievances reported by faculty at {GLB['name']}. "
    f"Classify each report into exactly ONE category from this list: {', '.join(CATEGORIES)}. "
    "Estimate severity as low, medium, or high (high = safety risk, total loss of a "
    "critical service, or many people affected). Write a single-sentence plain summary. "
    "Give a confidence 0-100. Set spam=true only if the text is clearly not a real "
    "infrastructure report (gibberish, a test, abuse). "
    'Respond ONLY with JSON: {"category": "...", "severity": "...", '
    '"summary": "...", "confidence": 0, "spam": false}'
)


def is_available() -> bool:
    return bool(Config.GROQ_API_KEY)


def classify(description: str, photo_b64: str | None = None,
             photo_mime: str = "image/jpeg") -> dict | None:
    if not is_available():
        return None

    user_content: object
    if photo_b64:
        model = Config.GROQ_MODEL_VISION
        user_content = [
            {"type": "text", "text": f"Report text: {description or '(none)'}"},
            {"type": "image_url",
             "image_url": {"url": f"data:{photo_mime};base64,{photo_b64}"}},
        ]
    else:
        model = Config.GROQ_MODEL_TEXT
        user_content = f"Report text: {description}"

    body = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": 400,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user_content},
        ],
    }
    try:
        r = requests.post(_URL, json=body, timeout=_TIMEOUT,
                          headers={"Authorization": f"Bearer {Config.GROQ_API_KEY}"})
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"]
        data = json.loads(raw)
    except Exception as e:  # noqa: BLE001
        print(f"[ai.engine] classify failed: {type(e).__name__}: {e}")
        return None

    category = str(data.get("category", "")).strip()
    if category not in CATEGORIES:
        # try a loose match (e.g. "IT/Network" vs "IT / Network")
        norm = category.replace(" ", "").lower()
        category = next((c for c in CATEGORIES if c.replace(" ", "").lower() == norm), None)
    if not category:
        return None

    severity = str(data.get("severity", "medium")).strip().lower()
    if severity not in SEVERITIES:
        severity = "medium"
    try:
        confidence = max(0, min(100, int(data.get("confidence", 60))))
    except (TypeError, ValueError):
        confidence = 60

    return {
        "category": category,
        "severity": severity,
        "summary": (str(data.get("summary", "")).strip() or description[:160]),
        "confidence": confidence,
        "spam": bool(data.get("spam", False)),
    }
```

- [ ] **Step 4: Sanity import** — `python -c "from ai import engine; print(engine.is_available())"` → `False`.

---

### Task 3: `services/classification_service.py`

**Files:**
- Create: `services/classification_service.py`
- Test: `tests/test_classification.py`, `tests/test_priority.py`

**Interfaces:**
- Produces:
  - `classify(description: str, photo_b64=None, photo_mime="image/jpeg") -> dict` — always returns `{"category": str|None, "severity": str, "ai_summary": str, "confidence": int, "spam_flag": bool, "source": "groq"|"keyword"}`. Tries `ai.engine.classify`; on `None` uses keyword logic.
  - `priority_score(g: dict, *, recurring_group: dict | None = None) -> int` — 0..100, the spec §9 formula. `g` keys used: `severity, category, status, created_at, location_type, sub_zone`.
  - `KEYWORDS: dict[str, list[str]]`, `SEVERITY_HIGH: list[str]`, `SEVERITY_LOW: list[str]` (module-level, for tests + reuse).

- [ ] **Step 1: Write `tests/test_classification.py`**

```python
from services import classification_service as cs


def test_keyword_picks_plumbing():
    r = cs.classify("Water is leaking from the pipe under the basin in the washroom")
    assert r["category"] == "Plumbing"
    assert r["source"] == "keyword"
    assert r["ai_summary"]


def test_keyword_picks_it_network():
    r = cs.classify("The projector in the classroom won't connect over HDMI and wifi is down")
    assert r["category"] == "IT / Network"


def test_keyword_high_severity_on_danger_words():
    r = cs.classify("Exposed live wire near the door, someone could get a shock")
    assert r["category"] in ("Electric", "Power")
    assert r["severity"] == "high"


def test_no_keyword_hit_leaves_category_none_but_summarises():
    r = cs.classify("Something seems off in the general area near here today")
    assert r["category"] is None
    assert r["severity"] == "medium"
    assert r["ai_summary"]


def test_spam_flag_on_gibberish():
    r = cs.classify("asdf asdf test test 123")
    assert r["spam_flag"] is True
```

- [ ] **Step 2: Write `tests/test_priority.py`**

```python
import time

from services.classification_service import priority_score


def _g(**kw):
    base = dict(severity="medium", category=None, status="reported",
                created_at=time.time(), location_type="hostels", sub_zone=None)
    base.update(kw)
    return base


def test_high_severity_electric_academics_scores_high():
    g = _g(severity="high", category="Electric", location_type="academics_block")
    # 45 (high) + 15 (electric) + 8 (academics) = 68
    assert priority_score(g) == 68


def test_low_floor_score():
    g = _g(severity="low", category="IT / Network", location_type="playground")
    # 10 + 3 + 0 = 13
    assert priority_score(g) == 13


def test_recurrence_adds_capped_boost():
    g = _g(severity="low", category="IT / Network", location_type="playground")
    grp = {"status": "active", "report_count": 30}
    # 13 + min(20, 2*30) = 33
    assert priority_score(g, recurring_group=grp) == 33


def test_age_boost_capped_and_clamped_to_100():
    old = time.time() - 40 * 86400
    g = _g(severity="high", category="Electric", status="verified",
           location_type="academics_block", created_at=old)
    # 45 + 15 + 8 + min(15, 40) = 83
    assert priority_score(g) == 83


def test_score_never_exceeds_100():
    old = time.time() - 999 * 86400
    g = _g(severity="high", category="Civil", location_type="academics_block", created_at=old)
    grp = {"status": "active", "report_count": 99}
    assert priority_score(g, recurring_group=grp) == 100
```

- [ ] **Step 3: Run both — fail.**

- [ ] **Step 4: Write `services/classification_service.py`**

```python
"""Grievance classification (Groq + keyword fallback) and priority scoring."""
from __future__ import annotations

import time

from ai import engine
from domain.constants import CATEGORIES

KEYWORDS: dict[str, list[str]] = {
    "Electric":     ["light", "bulb", "tube", "tubelight", "switch", "socket", "plug",
                     "wiring", "short circuit", "spark", "fan not", "fan is not",
                     "ceiling fan", "electrical", "wire"],
    "Power":        ["power cut", "no power", "power outage", "outage", "generator",
                     "ups", "voltage", "load shedding", "tripped", "mcb", "breaker",
                     "electricity is gone", "no electricity"],
    "Plumbing":     ["water", "tap", "faucet", "leak", "leaking", "pipe", "drain",
                     "flush", "toilet", "washroom", "restroom", "basin", "sink",
                     "overflow", "sewage", "clogged", "blocked drain", "no water"],
    "Civil":        ["wall", "ceiling", "crack", "cracked", "paint", "door", "window",
                     "floor", "tile", "seepage", "roof", "plaster", "broken glass",
                     "furniture", "desk", "bench", "chair", "table", "railing"],
    "Mechanical":   ["ac ", "a/c", "air condition", "cooler", "lift", "elevator",
                     "pump", "motor", "hvac", "exhaust", "chiller", "compressor"],
    "IT / Network": ["wifi", "wi-fi", "internet", "network", "lan", "projector",
                     "computer", " pc ", "monitor", "printer", "server", "port",
                     "hdmi", "smart board", "smartboard", "av system", "mic ",
                     "speaker", "sound system"],
}

SEVERITY_HIGH = ["danger", "dangerous", "unsafe", "fire", "smoke", "shock", "spark",
                 "flood", "flooding", "collapse", "collapsed", "injury", "injured",
                 "exposed wire", "live wire", "burning", "gas leak", "emergency",
                 "completely", "entire", "whole building", "no water at all"]
SEVERITY_LOW = ["minor", "small", "slight", "cosmetic", "sometimes", "occasionally",
                "a bit", "slightly"]

_SPAM_MARKERS = ["asdf", "qwer", "test test", "lorem ipsum", "aaaa", "1234567", "xyz xyz"]


def _keyword_classify(description: str) -> dict:
    t = f" {(description or '').lower()} "
    scores = {c: sum(1 for k in KEYWORDS[c] if k in t) for c in CATEGORIES}
    best = max(CATEGORIES, key=lambda c: scores[c])
    hits = scores[best]
    category = best if hits else None

    severity = "medium"
    if any(w in t for w in SEVERITY_HIGH):
        severity = "high"
    elif any(w in t for w in SEVERITY_LOW):
        severity = "low"

    alpha = sum(ch.isalpha() for ch in (description or ""))
    spam = alpha < 8 or any(m in t for m in _SPAM_MARKERS)

    summary = (description or "").strip()
    summary = (summary[:157] + "...") if len(summary) > 160 else summary

    return {
        "category": category,
        "severity": severity,
        "ai_summary": summary or "Infrastructure issue reported.",
        "confidence": 55 if hits else 15,
        "spam_flag": spam,
        "source": "keyword",
    }


def classify(description: str, photo_b64=None, photo_mime="image/jpeg") -> dict:
    ai = engine.classify(description, photo_b64=photo_b64, photo_mime=photo_mime)
    if ai:
        return {
            "category": ai["category"],
            "severity": ai["severity"],
            "ai_summary": ai["summary"],
            "confidence": ai["confidence"],
            "spam_flag": ai["spam"],
            "source": "groq",
        }
    return _keyword_classify(description)


# ── priority score (spec §9) ────────────────────────────────────────────────
_SEV = {"high": 45, "medium": 25, "low": 10}
_CAT_RISK = {"Electric": 15, "Power": 15, "Civil": 15, "Mechanical": 8,
             "Plumbing": 6, "IT / Network": 3}


def priority_score(g: dict, *, recurring_group: dict | None = None) -> int:
    score = _SEV.get(g.get("severity"), 25)
    score += _CAT_RISK.get(g.get("category"), 0)

    if recurring_group and recurring_group.get("status") == "active":
        score += min(20, 2 * int(recurring_group.get("report_count", 0)))

    if g.get("status") in ("reported", "verified") and g.get("created_at"):
        days = (time.time() - g["created_at"]) / 86400
        score += min(15, int(days))

    lt = g.get("location_type")
    if lt == "academics_block":
        score += 8
    elif lt == "mess_canteen":
        score += 6
    elif lt == "hostels":
        score += 4
    if g.get("sub_zone") == "Security":
        score += 8

    return max(0, min(100, score))
```

- [ ] **Step 5: Run both — pass.** `pytest tests/test_classification.py tests/test_priority.py -q`

---

### Task 4: `services/duplicate_service.py`

**Files:**
- Create: `services/duplicate_service.py`
- Test: `tests/test_duplicate_service.py`

**Interfaces:**
- Consumes: `db.grievances.find_recurring_candidates(location_label, category, since_ts) -> list[dict]`.
- Produces: `find_recurring(location_label: str, category: str | None, reporter_id: int | None, now: float | None = None) -> dict` →
  `{"same_reporter_recent": bool, "candidates": list[dict], "match": bool}`.
  - `candidates`: non-closed grievances, same label + category, `created_at >= now - RECURRING_WINDOW_DAYS*86400`, excluding none.
  - `same_reporter_recent`: any candidate by `reporter_id` with `created_at >= now - 86400`.
  - `match`: `bool(candidates)` and not `same_reporter_recent` — i.e. a groupable recurrence exists.
  - If `category` is `None` → always `{"same_reporter_recent": False, "candidates": [], "match": False}` (can't match without a category).

- [ ] **Step 1: Write `tests/test_duplicate_service.py`**

```python
import time

from db import grievances, users
from services import duplicate_service as ds
from services.auth_service import hash_pin


def _mk(reporter_id, label, category, created_offset_days=0.0):
    g = grievances.insert(reporter_id=reporter_id, reporter_name="x", title="t",
                          description="a broken thing here now", location_type="hostels",
                          location_label=label, category=category)
    if created_offset_days:
        grievances.update(g["id"], created_at=time.time() - created_offset_days * 86400)
    return g


def test_no_category_never_matches(memstore):
    u = users.create("a", "A", "reporter", hash_pin("1"))
    _mk(u["id"], "Hostels", None)
    r = ds.find_recurring("Hostels", None, u["id"])
    assert r == {"same_reporter_recent": False, "candidates": [], "match": False}


def test_different_reporter_same_place_and_category_matches(memstore):
    u1 = users.create("u1", "U1", "reporter", hash_pin("1"))
    u2 = users.create("u2", "U2", "reporter", hash_pin("1"))
    _mk(u1["id"], "Hostels", "Plumbing")
    r = ds.find_recurring("Hostels", "Plumbing", u2["id"])
    assert r["match"] is True
    assert len(r["candidates"]) == 1
    assert r["same_reporter_recent"] is False


def test_same_reporter_within_24h_is_true_duplicate(memstore):
    u = users.create("u", "U", "reporter", hash_pin("1"))
    _mk(u["id"], "Playground", "Civil")
    r = ds.find_recurring("Playground", "Civil", u["id"])
    assert r["same_reporter_recent"] is True
    assert r["match"] is False


def test_outside_window_no_match(memstore):
    u1 = users.create("u1", "U1", "reporter", hash_pin("1"))
    u2 = users.create("u2", "U2", "reporter", hash_pin("1"))
    _mk(u1["id"], "Mess / Canteen", "Mechanical", created_offset_days=20)
    r = ds.find_recurring("Mess / Canteen", "Mechanical", u2["id"])
    assert r["candidates"] == []
    assert r["match"] is False
```

- [ ] **Step 2: Run — fails.**

- [ ] **Step 3: Write `services/duplicate_service.py`**

```python
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
```

- [ ] **Step 4: Run — passes.**

---

### Task 5: `services/grievance_service.py` — submit pipeline

**Files:**
- Create: `services/grievance_service.py`
- Test: `tests/test_grievance_pipeline.py`

**Interfaces:**
- Consumes: `validation_service.validate_submission`, `classification_service.classify` + `priority_score`, `duplicate_service.find_recurring`, `db.grievances`, `db.evidence`, `db.timeline`, `db.recurring`, `db.users.get_by_id`, `storage_service.upload_image`.
- Produces:
  - `SubmissionError(Exception)` with `.errors: list[str]`
  - `submit(sub: dict) -> dict` — `sub` keys: `reporter_id`(int), `description`, `location_type`, `block_no`, `floor`, `room`, `sub_zone`, `location_label`, `photo_b64`, `photo_mime`, and optional pre-computed `ai` = `{category, severity, ai_summary, confidence, spam_flag}` (from `/report/analyze`). Returns
    `{"code": str, "grievance_id": int, "category": str|None, "recurring": {"group_id": int, "report_count": int} | None, "spam_flag": bool}`.
  - Raises `SubmissionError` on validation failure or true-duplicate.
  - Pipeline order exactly: validate → classify (reuse `sub['ai']` if present) → `find_recurring` (raise if `same_reporter_recent`) → store photo → insert grievance (with `priority_score`) → `evidence('report')` → set `primary_photo_url`/`thumbnail_url` to `/photo/<evidence_id>` → `timeline('created')` → recurring group create/attach/bump + `merged_recurring` timeline events.

- [ ] **Step 1: Write `tests/test_grievance_pipeline.py`**

```python
import pytest

from db import evidence, grievances, recurring, timeline, users
from services import grievance_service as gs
from services.auth_service import hash_pin


def _sub(reporter_id, **kw):
    base = dict(
        reporter_id=reporter_id,
        description="The ceiling fan in this room has completely stopped working",
        location_type="academics_block", block_no="Block B", floor="2nd Floor",
        room="204", sub_zone=None,
        location_label="Academics Block > Block B > 2nd Floor > Room 204",
        photo_b64="aGVsbG8gd29ybGQ=", photo_mime="image/jpeg",
    )
    base.update(kw)
    return base


def test_happy_path_creates_grievance_evidence_timeline(memstore):
    u = users.create("f1", "Faculty One", "reporter", hash_pin("1"))
    out = gs.submit(_sub(u["id"]))
    assert out["code"].startswith("GLB-CAMP-")
    assert out["recurring"] is None
    g = grievances.get_by_code(out["code"])
    assert g["status"] == "reported"
    assert g["category"] in ("Electric", "Power")     # keyword: "fan ... stopped"
    assert g["priority_score"] > 0
    assert g["primary_photo_url"] == f"/photo/{evidence.list_for(g['id'])[0]['id']}"
    assert [e["kind"] for e in evidence.list_for(g["id"])] == ["report"]
    assert [e["event_type"] for e in timeline.list_for(g["id"])] == ["created"]


def test_validation_error_raises(memstore):
    u = users.create("f2", "F2", "reporter", hash_pin("1"))
    with pytest.raises(gs.SubmissionError) as ei:
        gs.submit(_sub(u["id"], description="nope"))
    assert ei.value.errors


def test_same_reporter_24h_duplicate_raises(memstore):
    u = users.create("f3", "F3", "reporter", hash_pin("1"))
    gs.submit(_sub(u["id"], description="Water leaking from the pipe under the basin"))
    with pytest.raises(gs.SubmissionError):
        gs.submit(_sub(u["id"], description="Water leaking from the pipe under the basin"))


def test_second_reporter_forms_recurring_group(memstore):
    u1 = users.create("a", "A", "reporter", hash_pin("1"))
    u2 = users.create("b", "B", "reporter", hash_pin("1"))
    d = "Water is leaking from the pipe under the basin in this washroom"
    label = "Academics Block > Block B > 2nd Floor > Room 204"
    gs.submit(_sub(u1["id"], description=d, location_label=label))
    out2 = gs.submit(_sub(u2["id"], description=d, location_label=label))
    assert out2["recurring"] is not None
    grp = recurring.get(out2["recurring"]["group_id"])
    assert grp["report_count"] == 2
    assert grp["reporter_count"] == 2
    # both grievances point at the group
    codes = [x for x in grievances.list_query() if x["recurring_group_id"] == grp["id"]]
    assert len(codes) == 2
    # a merged_recurring event was logged on both
    for g in codes:
        types = [e["event_type"] for e in timeline.list_for(g["id"])]
        assert "merged_recurring" in types


def test_precomputed_ai_is_used(memstore):
    u = users.create("f4", "F4", "reporter", hash_pin("1"))
    out = gs.submit(_sub(u["id"], ai={"category": "IT / Network", "severity": "high",
                                      "ai_summary": "Projector dead", "confidence": 90,
                                      "spam_flag": False}))
    assert grievances.get_by_code(out["code"])["category"] == "IT / Network"
    assert grievances.get_by_code(out["code"])["ai_summary"] == "Projector dead"
```

- [ ] **Step 2: Run — fails.**

- [ ] **Step 3: Write `services/grievance_service.py`**

```python
"""The faculty grievance submission pipeline."""
from __future__ import annotations

import time

from db import evidence, grievances, recurring, timeline, users
from domain.constants import CATEGORIES
from services import classification_service, duplicate_service, storage_service
from services.validation_service import validate_submission


class SubmissionError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def _group_title(label: str, category: str) -> str:
    tail = label.split(" > ")[-1]
    return f"{tail} - {category}"


def submit(sub: dict) -> dict:
    # 1. validate
    errors = validate_submission(sub)
    if errors:
        raise SubmissionError(errors)

    reporter = users.get_by_id(sub["reporter_id"])
    reporter_name = reporter["display_name"] if reporter else "Unknown"
    description = sub["description"].strip()
    label = sub["location_label"].strip()

    # 2. classify (reuse the wizard's /report/analyze result if given)
    pre = sub.get("ai") or {}
    if pre.get("category") in CATEGORIES or pre.get("ai_summary"):
        cls = {
            "category": pre.get("category") if pre.get("category") in CATEGORIES else None,
            "severity": pre.get("severity", "medium"),
            "ai_summary": pre.get("ai_summary", description[:160]),
            "confidence": int(pre.get("confidence", 60) or 60),
            "spam_flag": bool(pre.get("spam_flag", False)),
        }
    else:
        cls = classification_service.classify(
            description, photo_b64=sub.get("photo_b64"),
            photo_mime=sub.get("photo_mime", "image/jpeg"),
        )

    # 3. recurring / duplicate
    dup = duplicate_service.find_recurring(label, cls["category"], sub["reporter_id"])
    if dup["same_reporter_recent"]:
        raise SubmissionError([
            "You already reported this exact issue in the last 24 hours. "
            "The admin can see it — no need to report it again."
        ])

    # 4. store photo
    photo_url = storage_service.upload_image(sub.get("photo_b64") or "",
                                             sub.get("photo_mime", "image/jpeg"))

    # 5. insert grievance
    g_seed = {
        "severity": cls["severity"], "category": cls["category"], "status": "reported",
        "created_at": time.time(), "location_type": sub["location_type"],
        "sub_zone": sub.get("sub_zone"),
    }
    priority = classification_service.priority_score(g_seed)

    title = cls["ai_summary"][:120] if cls["ai_summary"] else description[:120]
    g = grievances.insert(
        reporter_id=sub["reporter_id"], reporter_name=reporter_name,
        title=title, description=description,
        category=cls["category"], severity=cls["severity"],
        priority_score=priority,
        location_type=sub["location_type"], block_no=sub.get("block_no"),
        floor=sub.get("floor"), room=sub.get("room"), sub_zone=sub.get("sub_zone"),
        location_label=label,
        ai_summary=cls["ai_summary"], ai_confidence=cls["confidence"],
    )

    # 6. report-photo evidence + backfill the served URL onto the grievance
    ev = evidence.add(g["id"], "report", image_url=photo_url,
                      thumbnail_url=photo_url, uploaded_by=reporter_name)
    served = f"/photo/{ev['id']}"
    grievances.update(g["id"], primary_photo_url=served, thumbnail_url=served)

    timeline.add(g["id"], "created", actor=reporter_name, actor_role="reporter",
                 note=f"Reported via {cls.get('source', 'form')}")

    # 7. recurring group
    recurring_out = None
    if dup["match"]:
        grp = recurring.find_active(label, cls["category"])
        first_partner = dup["candidates"][0]
        if grp is None:
            grp = recurring.create(label, cls["category"],
                                   _group_title(label, cls["category"]),
                                   primary_grievance_id=first_partner["id"],
                                   first_ts=first_partner.get("created_at") or time.time())
            # attach the earlier partner too
            grievances.update(first_partner["id"], recurring_group_id=grp["id"])
            recurring.bump(grp["id"], last_ts=first_partner.get("created_at") or time.time(),
                           add_reporter=True)
            timeline.add(first_partner["id"], "merged_recurring", actor="system",
                         to_value=grp["title"], note="Grouped as a recurring issue")

        prior_reporters = {c["reporter_id"] for c in dup["candidates"]}
        grievances.update(g["id"], recurring_group_id=grp["id"])
        grp = recurring.bump(grp["id"], last_ts=time.time(),
                             add_reporter=sub["reporter_id"] not in prior_reporters)
        timeline.add(g["id"], "merged_recurring", actor="system",
                     to_value=grp["title"], note="Grouped as a recurring issue")
        recurring_out = {"group_id": grp["id"], "report_count": grp["report_count"]}

    return {
        "code": g["code"], "grievance_id": g["id"], "category": cls["category"],
        "recurring": recurring_out, "spam_flag": cls["spam_flag"],
    }
```

- [ ] **Step 4: Run — pass.** `pytest tests/test_grievance_pipeline.py -q`
Expected: 5 passed. (If `test_second_reporter_forms_recurring_group` shows `report_count == 2` — the bump for the earlier partner + the new one.)

---

### Task 6: Faculty blueprint — auth guard, home, notices, photo serving

**Files:**
- Create: `blueprints/faculty/__init__.py`, `templates/faculty/home.html`, `templates/faculty/notices.html`
- Modify: `app.py` (register blueprint), `templates/base_faculty.html`

**Interfaces:**
- Consumes: `db.grievances.list_for_reporter`, `db.notices.list_published`, `db.evidence`, `db.grievances.get_by_id`.
- Produces routes (blueprint `faculty`, no url_prefix):
  - `before_request` → 302 `/login` if `g.current_user` is None; if role `admin` and path is `/` → 302 `/admin`.
  - `GET /` → `faculty/home.html`
  - `GET /notices` → `faculty/notices.html`
  - `GET /photo/<int:eid>` → serves the evidence image (owner reporter or admin only); data-URI → bytes, http URL → redirect, missing → 404.

- [ ] **Step 1: Write `blueprints/faculty/__init__.py`**

```python
"""Faculty PWA blueprint: home, report, my-reports, grievance detail, notices."""
import base64

from flask import (Blueprint, abort, g, redirect, render_template, request, Response)

from db import evidence, grievances, notices

bp = Blueprint("faculty", __name__, template_folder="../../templates")


@bp.before_request
def _require_login():
    if not g.get("current_user"):
        return redirect("/login")
    if g.current_user["role"] == "admin" and request.path == "/":
        return redirect("/admin")


def _my_open_count(uid_name):
    rows = grievances.list_for_reporter(_uid())
    return sum(1 for r in rows if r["status"] not in ("closed", "admin_verified"))


def _uid():
    from db import users
    u = users.get_by_username(g.current_user["username"])
    return u["id"] if u else -1


@bp.get("/")
def home():
    uid = _uid()
    mine = grievances.list_for_reporter(uid)
    open_count = sum(1 for r in mine if r["status"] not in ("closed", "admin_verified"))
    latest = notices.list_published()[:1]
    return render_template("faculty/home.html", open_count=open_count,
                           recent=mine[:3], latest_notice=(latest[0] if latest else None))


@bp.get("/notices")
def notices_page():
    return render_template("faculty/notices.html", notices=notices.list_published())


@bp.get("/photo/<int:eid>")
def photo(eid):
    all_ev = [e for lst in
              (evidence.list_for(gr["id"]) for gr in grievances.list_query(limit=100000))
              for e in lst]
    ev = next((e for e in all_ev if e["id"] == eid), None)
    if not ev:
        abort(404)
    gr = grievances.get_by_id(ev["grievance_id"])
    if g.current_user["role"] != "admin" and gr["reporter_id"] != _uid():
        abort(403)
    url = ev.get("image_url") or ""
    if url.startswith("http"):
        return redirect(url)
    if url.startswith("data:"):
        header, b64 = url.split(",", 1)
        mime = header.split(":", 1)[1].split(";", 1)[0]
        return Response(base64.b64decode(b64), mimetype=mime,
                        headers={"Cache-Control": "private, max-age=86400"})
    abort(404)
```

- [ ] **Step 2: Register in `app.py`** — after the `auth_bp` registration:

```python
    from blueprints.faculty import bp as faculty_bp
    app.register_blueprint(faculty_bp)
```

- [ ] **Step 3: Rewrite `templates/base_faculty.html`**

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="{{ GLB.theme_navy }}">
  <link rel="manifest" href="{{ url_for('static', filename='manifest.webmanifest') }}">
  <link rel="apple-touch-icon" href="{{ url_for('static', filename='icons/icon-192.png') }}">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-title" content="UniPulse">
  <title>{% block title %}UniPulse{% endblock %} &middot; {{ GLB.short }}</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='css/app.css') }}">
</head>
<body class="faculty">
  <header class="topbar">
    <strong>UniPulse</strong>
    {% if current_user %}<a href="/logout" class="right">Log out</a>{% endif %}
  </header>
  <main class="app-main">{% block content %}{% endblock %}</main>
  {% if current_user and current_user.role == 'reporter' %}
  <nav class="bottomnav">
    <a href="/" class="{{ 'on' if request.path == '/' }}">Home</a>
    <a href="/report" class="{{ 'on' if request.path == '/report' }}">Report</a>
    <a href="/my-reports" class="{{ 'on' if request.path.startswith('/my-reports') }}">My Reports</a>
    <a href="/notices" class="{{ 'on' if request.path == '/notices' }}">Notices</a>
  </nav>
  {% endif %}
  <script>
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("{{ url_for('static', filename='service-worker.js') }}");
    }
  </script>
  {% block scripts %}{% endblock %}
</body>
</html>
```

- [ ] **Step 4: Append to `static/css/app.css`**

```css
.app-main { padding-bottom: 72px; }
.bottomnav { position:fixed; left:0; right:0; bottom:0; display:flex; background:#fff;
  border-top:1px solid var(--line); }
.bottomnav a { flex:1; text-align:center; padding:12px 4px; font-size:12.5px; color:var(--muted);
  text-decoration:none; }
.bottomnav a.on { color:var(--glb-blue); font-weight:700; }
.card { background:#fff; border:1px solid var(--line); border-radius:10px; padding:14px 16px; margin:12px 0; }
.cta { display:block; text-align:center; background:var(--glb-blue); color:#fff; padding:18px;
  border-radius:12px; font-size:17px; font-weight:700; text-decoration:none; margin:16px 0; }
.chip { display:inline-block; padding:2px 9px; border-radius:999px; font-size:12px; font-weight:600; }
.chip.reported{background:#eef;color:#334;} .chip.verified{background:#e7f0ff;color:#1e5fbf;}
.chip.assigned,.chip.in_progress{background:#fff3e0;color:#9a5b00;}
.chip.resolved,.chip.admin_verified{background:#e7f7ec;color:#1b7f3b;} .chip.closed{background:#eee;color:#555;}
.step { display:none; } .step.active { display:block; }
.pill-row { display:flex; flex-wrap:wrap; gap:8px; }
.pill { border:1px solid var(--line); background:#fff; border-radius:999px; padding:10px 14px; cursor:pointer; }
.pill.sel { border-color:var(--glb-blue); background:#eaf1ff; font-weight:700; }
.timeline li { margin:8px 0; padding-left:16px; border-left:2px solid var(--line); }
.timeline li.done { border-color:var(--glb-blue); }
img.evidence { max-width:100%; border-radius:8px; border:1px solid var(--line); }
```

- [ ] **Step 5: Write `templates/faculty/home.html`**

```html
{% extends "base_faculty.html" %}
{% block title %}Home{% endblock %}
{% block content %}
<h2>Hi, {{ current_user.display_name }}</h2>
<p class="muted">Report a campus infrastructure problem and we'll route it to the right team.</p>
<a class="cta" href="/report">+ Report an Issue</a>
<div class="card">
  <strong>{{ open_count }}</strong> of your reports {{ 'is' if open_count == 1 else 'are' }} still open.
  <a href="/my-reports">View all &rsaquo;</a>
</div>
{% if latest_notice %}
<div class="card">
  <div class="muted" style="font-size:12px">CAMPUS NOTICE</div>
  <strong>{{ latest_notice.title }}</strong>
  <p>{{ latest_notice.body }}</p>
  <a href="/notices">All notices &rsaquo;</a>
</div>
{% endif %}
{% if recent %}
<h3>Recent</h3>
{% for r in recent %}
<a class="card" style="display:block;text-decoration:none;color:inherit" href="/grievance/{{ r.code }}">
  <span class="chip {{ r.status }}">{{ r.status.replace('_',' ') }}</span>
  <strong>{{ r.code }}</strong><br>
  <span class="muted">{{ r.category or 'Uncategorised' }} &middot; {{ r.location_label }}</span>
</a>
{% endfor %}
{% endif %}
{% endblock %}
```

- [ ] **Step 6: Write `templates/faculty/notices.html`**

```html
{% extends "base_faculty.html" %}
{% block title %}Notices{% endblock %}
{% block content %}
<h2>Campus notices</h2>
{% for n in notices %}
<div class="card">
  <strong>{{ n.title }}</strong>
  <p>{{ n.body }}</p>
</div>
{% else %}
<p class="muted">No notices right now.</p>
{% endfor %}
{% endblock %}
```

- [ ] **Step 7: Boot check** — `python -c "from app import create_app; c=create_app().test_client(); c.post('/login',data={'username':'prof.rao','pin':'1234'}); r=c.get('/'); print(r.status_code); assert r.status_code==200 and b'Report an Issue' in r.data"` → `200`.

---

### Task 7: Report wizard — `/report`, `/report/analyze`, `/report` POST

**Files:**
- Create: `templates/faculty/report.html`, `static/js/report.js`
- Modify: `blueprints/faculty/__init__.py`

**Interfaces:**
- Consumes: `db.locations.picker`, `services.classification_service.classify`, `services.grievance_service.submit` + `SubmissionError`, `domain.models.build_location_label`, `domain.constants.LOCATION_TYPES`.
- Produces routes:
  - `GET /report` → `faculty/report.html` with `picker` + `type_names` in context.
  - `POST /report/analyze` (JSON in: `{description, photo_b64, photo_mime}`) → `{ai_summary, category, severity, spam_flag, source}`.
  - `POST /report` (JSON in: `{description, location_type, block_no, floor, room, sub_zone, photo_b64, photo_mime, ai:{...}}`) → 200 `{code, recurring}` or 400 `{errors:[...]}`.

- [ ] **Step 1: Add routes to `blueprints/faculty/__init__.py`**

```python
from domain.constants import LOCATION_TYPES
from domain.models import build_location_label
from services import classification_service, grievance_service
from db import locations

_TYPE_NAMES = {t["key"]: t["name"] for t in LOCATION_TYPES}


@bp.get("/report")
def report_page():
    return render_template("faculty/report.html", picker=locations.picker(),
                           type_names=_TYPE_NAMES)


@bp.post("/report/analyze")
def report_analyze():
    d = request.get_json(silent=True) or {}
    res = classification_service.classify(
        (d.get("description") or "").strip(),
        photo_b64=d.get("photo_b64"), photo_mime=d.get("photo_mime", "image/jpeg"),
    )
    return {"ai_summary": res["ai_summary"], "category": res["category"],
            "severity": res["severity"], "spam_flag": res["spam_flag"],
            "source": res["source"]}


@bp.post("/report")
def report_submit():
    d = request.get_json(silent=True) or {}
    label = build_location_label(
        d.get("location_type"), d.get("block_no"), d.get("floor"),
        d.get("room"), d.get("sub_zone"), type_names=_TYPE_NAMES,
    )
    sub = {
        "reporter_id": _uid(),
        "description": (d.get("description") or "").strip(),
        "location_type": d.get("location_type"),
        "block_no": d.get("block_no"), "floor": d.get("floor"),
        "room": d.get("room"), "sub_zone": d.get("sub_zone"),
        "location_label": label,
        "photo_b64": d.get("photo_b64"), "photo_mime": d.get("photo_mime", "image/jpeg"),
        "ai": d.get("ai"),
    }
    try:
        out = grievance_service.submit(sub)
    except grievance_service.SubmissionError as e:
        return {"errors": e.errors}, 400
    return {"code": out["code"], "recurring": out["recurring"]}
```

- [ ] **Step 2: Write `templates/faculty/report.html`**

```html
{% extends "base_faculty.html" %}
{% block title %}Report an Issue{% endblock %}
{% block content %}
<h2>Report an Issue</h2>
<div id="wiz"
     data-picker='{{ picker | tojson }}'
     data-typenames='{{ type_names | tojson }}'>

  <div class="step active" data-step="1">
    <label>1. Photo of the problem</label>
    <input type="file" id="photo" accept="image/*" capture="environment">
    <img id="preview" class="evidence" style="display:none;margin-top:10px">
    <button id="to2" style="margin-top:14px">Next</button>
  </div>

  <div class="step" data-step="2">
    <label>2. Where is it?</label>
    <div class="pill-row" id="type-pills"></div>
    <div id="drill"></div>
    <button id="to3" style="margin-top:14px">Next</button>
  </div>

  <div class="step" data-step="3">
    <label>3. Describe the problem</label>
    <textarea id="desc" rows="4" placeholder="e.g. The projector has stopped working again"></textarea>
    <button id="to4" style="margin-top:14px">Review</button>
  </div>

  <div class="step" data-step="4">
    <label>4. What we understood</label>
    <div class="card" id="ai-box">Analysing&hellip;</div>
    <button id="submit">Submit report</button>
    <button id="back3" style="background:#eee;color:#333">Edit description</button>
  </div>

  <div class="step" data-step="done">
    <div class="card" id="done-box"></div>
    <a class="cta" href="/my-reports">Go to My Reports</a>
  </div>
</div>
{% endblock %}
{% block scripts %}<script src="{{ url_for('static', filename='js/report.js') }}"></script>{% endblock %}
```

- [ ] **Step 3: Write `static/js/report.js`**

```javascript
(() => {
  const wiz = document.getElementById("wiz");
  const picker = JSON.parse(wiz.dataset.picker);
  const state = { photo_b64: null, photo_mime: "image/jpeg", type: null,
                  block_no: null, floor: null, room: null, sub_zone: null,
                  description: "", ai: null };

  const show = (s) => document.querySelectorAll(".step").forEach(
    el => el.classList.toggle("active", el.dataset.step === String(s)));

  // Step 1 — photo
  document.getElementById("photo").addEventListener("change", (e) => {
    const f = e.target.files[0];
    if (!f) return;
    state.photo_mime = f.type || "image/jpeg";
    const r = new FileReader();
    r.onload = () => {
      state.photo_b64 = r.result.split(",")[1];
      const img = document.getElementById("preview");
      img.src = r.result; img.style.display = "block";
    };
    r.readAsDataURL(f);
  });
  document.getElementById("to2").onclick = () => {
    if (!state.photo_b64) return alert("Please add a photo first.");
    show(2);
  };

  // Step 2 — location
  const typePills = document.getElementById("type-pills");
  picker.types.forEach((t) => {
    const b = document.createElement("button");
    b.className = "pill"; b.textContent = t.name; b.dataset.key = t.key;
    b.onclick = () => {
      typePills.querySelectorAll(".pill").forEach(p => p.classList.remove("sel"));
      b.classList.add("sel");
      state.type = t.key; state.block_no = state.floor = state.room = state.sub_zone = null;
      renderDrill(t);
    };
    typePills.appendChild(b);
  });
  function sel(label, opts, onpick) {
    const wrap = document.createElement("div");
    wrap.innerHTML = `<label>${label}</label>`;
    const s = document.createElement("select");
    s.innerHTML = `<option value="">Select&hellip;</option>` +
      opts.map(o => `<option>${o}</option>`).join("");
    s.onchange = () => onpick(s.value || null);
    wrap.appendChild(s); return wrap;
  }
  function renderDrill(t) {
    const d = document.getElementById("drill"); d.innerHTML = "";
    if (t.key === "academics_block") {
      d.appendChild(sel("Block", picker.academics_blocks, v => state.block_no = v));
      d.appendChild(sel("Floor", picker.academics_floors, v => state.floor = v));
      const rm = document.createElement("div");
      rm.innerHTML = `<label>Room</label><input id="room" placeholder="e.g. 204">`;
      rm.querySelector("input").oninput = e => state.room = e.target.value.trim() || null;
      d.appendChild(rm);
    } else if (t.key === "outer_area") {
      d.appendChild(sel("Sub-zone", picker.outer_area_subzones, v => state.sub_zone = v));
    }
  }
  document.getElementById("to3").onclick = () => {
    if (!state.type) return alert("Pick a location type.");
    if (state.type === "academics_block" && !state.block_no)
      return alert("Pick a block.");
    if (state.type === "outer_area" && !state.sub_zone)
      return alert("Pick a sub-zone.");
    show(3);
  };

  // Step 3 -> analyze
  document.getElementById("back3").onclick = () => show(3);
  document.getElementById("to4").onclick = async () => {
    state.description = document.getElementById("desc").value.trim();
    if (state.description.length < 10) return alert("Add a bit more detail (min 10 chars).");
    show(4);
    const box = document.getElementById("ai-box");
    box.textContent = "Analysing…";
    try {
      const res = await fetch("/report/analyze", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description: state.description,
                               photo_b64: state.photo_b64, photo_mime: state.photo_mime }),
      });
      const a = await res.json();
      state.ai = a;
      box.innerHTML = `<p>${a.ai_summary}</p>
        <p class="muted">Category: <strong>${a.category || "needs review"}</strong>
        &middot; Severity: <strong>${a.severity}</strong></p>` +
        (a.spam_flag ? `<p class="error">This doesn't look like an infrastructure
         report - you can still submit if it is.</p>` : "");
    } catch (e) {
      box.textContent = "Could not analyse - you can still submit.";
      state.ai = null;
    }
  };

  // Step 4 -> submit
  document.getElementById("submit").onclick = async () => {
    const btn = document.getElementById("submit");
    btn.disabled = true; btn.textContent = "Submitting…";
    try {
      const res = await fetch("/report", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          description: state.description, location_type: state.type,
          block_no: state.block_no, floor: state.floor, room: state.room,
          sub_zone: state.sub_zone, photo_b64: state.photo_b64,
          photo_mime: state.photo_mime, ai: state.ai,
        }),
      });
      const out = await res.json();
      if (!res.ok) { alert((out.errors || ["Something went wrong"]).join("\n"));
                     btn.disabled = false; btn.textContent = "Submit report"; return; }
      const box = document.getElementById("done-box");
      box.innerHTML = `<h3>Reported as ${out.code}</h3>` + (out.recurring
        ? `<p>This looks related to ${out.recurring.report_count - 1} other report(s)
           for this location - the admin sees them as one recurring issue.</p>`
        : `<p>The campus admin will review it shortly.</p>`);
      show("done");
    } catch (e) {
      alert("Network error - please try again.");
      btn.disabled = false; btn.textContent = "Submit report";
    }
  };
})();
```

- [ ] **Step 4: Add `tests/test_faculty_routes.py`** (report flow portion)

```python
def _login(client, u="prof.rao", p="1234"):
    return client.post("/login", data={"username": u, "pin": p})


def test_report_page_renders(client):
    _login(client)
    r = client.get("/report")
    assert r.status_code == 200
    assert b"Report an Issue" in r.data


def test_analyze_returns_summary(client):
    _login(client)
    r = client.post("/report/analyze", json={
        "description": "Water leaking from the pipe under the basin in the washroom"})
    j = r.get_json()
    assert j["category"] == "Plumbing"
    assert j["ai_summary"]


def test_submit_happy_path(client):
    _login(client)
    r = client.post("/report", json={
        "description": "The ceiling fan has completely stopped working in this room",
        "location_type": "academics_block", "block_no": "Block B",
        "floor": "2nd Floor", "room": "204",
        "photo_b64": "aGVsbG8=", "photo_mime": "image/jpeg",
    })
    assert r.status_code == 200
    assert r.get_json()["code"].startswith("GLB-CAMP-")


def test_submit_validation_error(client):
    _login(client)
    r = client.post("/report", json={"description": "no", "location_type": "hostels",
                                     "photo_b64": "x"})
    assert r.status_code == 400
    assert r.get_json()["errors"]


def test_report_requires_login(client):
    r = client.get("/report")
    assert r.status_code == 302 and "/login" in r.headers["Location"]
```

- [ ] **Step 5: Run** — `pytest tests/test_faculty_routes.py -q` → PASS.

---

### Task 8: My Reports + grievance detail

**Files:**
- Create: `templates/faculty/my_reports.html`, `templates/faculty/grievance_detail.html`
- Modify: `blueprints/faculty/__init__.py`

**Interfaces:**
- Consumes: `db.grievances.list_for_reporter`, `db.grievances.get_by_code`, `db.timeline.list_for`, `db.evidence.list_for`, `db.recurring.get`, `domain.constants.STATUSES`.
- Produces routes:
  - `GET /my-reports` → `faculty/my_reports.html`
  - `GET /my-reports/data` → `{grievances: [ {code, category, status, location_label, created_at, priority_score, recurring_group_id} ]}` (newest first, this reporter only)
  - `GET /grievance/<code>` → `faculty/grievance_detail.html`; 404 if not found, 403 if not owner and not admin. Context: `g` (grievance), `timeline`, `evidence`, `group` (recurring or None), `steps` (list of `{key,label,done,current}` from `STATUSES` up to `closed`).

- [ ] **Step 1: Add routes to `blueprints/faculty/__init__.py`**

```python
from db import recurring, timeline
from domain.constants import STATUSES

_STEP_LABELS = {
    "reported": "Reported", "verified": "Verified", "assigned": "Assigned",
    "in_progress": "In progress", "resolved": "Resolved",
    "admin_verified": "Admin verified", "closed": "Closed",
}


@bp.get("/my-reports")
def my_reports_page():
    return render_template("faculty/my_reports.html")


@bp.get("/my-reports/data")
def my_reports_data():
    rows = grievances.list_for_reporter(_uid())
    return {"grievances": [
        {"code": r["code"], "category": r["category"], "status": r["status"],
         "location_label": r["location_label"], "created_at": r["created_at"],
         "priority_score": r["priority_score"],
         "recurring_group_id": r["recurring_group_id"]}
        for r in rows
    ]}


@bp.get("/grievance/<code>")
def grievance_detail(code):
    gr = grievances.get_by_code(code)
    if not gr:
        abort(404)
    if g.current_user["role"] != "admin" and gr["reporter_id"] != _uid():
        abort(403)
    idx = STATUSES.index(gr["status"]) if gr["status"] in STATUSES else 0
    steps = [{"key": s, "label": _STEP_LABELS[s],
              "done": i < idx, "current": i == idx}
             for i, s in enumerate(STATUSES)]
    group = recurring.get(gr["recurring_group_id"]) if gr["recurring_group_id"] else None
    return render_template("faculty/grievance_detail.html", g=gr,
                           timeline=timeline.list_for(gr["id"]),
                           evidence=evidence.list_for(gr["id"]),
                           group=group, steps=steps)
```

- [ ] **Step 2: Write `templates/faculty/my_reports.html`**

```html
{% extends "base_faculty.html" %}
{% block title %}My Reports{% endblock %}
{% block content %}
<h2>My Reports</h2>
<div id="list"><p class="muted">Loading&hellip;</p></div>
{% endblock %}
{% block scripts %}
<script>
fetch("/my-reports/data").then(r => r.json()).then(({grievances}) => {
  const el = document.getElementById("list");
  if (!grievances.length) { el.innerHTML = "<p class='muted'>No reports yet.</p>"; return; }
  el.innerHTML = grievances.map(g => `
    <a class="card" style="display:block;text-decoration:none;color:inherit" href="/grievance/${g.code}">
      <span class="chip ${g.status}">${g.status.replace('_',' ')}</span>
      <strong>${g.code}</strong>
      ${g.recurring_group_id ? '<span class="chip verified">recurring</span>' : ''}<br>
      <span class="muted">${g.category || 'Uncategorised'} &middot; ${g.location_label}</span>
    </a>`).join("");
});
</script>
{% endblock %}
```

- [ ] **Step 3: Write `templates/faculty/grievance_detail.html`**

```html
{% extends "base_faculty.html" %}
{% block title %}{{ g.code }}{% endblock %}
{% block content %}
<h2>{{ g.code }} <span class="chip {{ g.status }}">{{ g.status.replace('_',' ') }}</span></h2>
<p class="muted">{{ g.category or 'Uncategorised' }} &middot; severity {{ g.severity or 'n/a' }}
  &middot; {{ g.location_label }}</p>

{% if g.primary_photo_url %}<img class="evidence" src="{{ g.primary_photo_url }}" alt="reported photo">{% endif %}

<div class="card">
  <strong>What was reported</strong>
  <p>{{ g.description }}</p>
  {% if g.ai_summary %}<p class="muted">AI summary: {{ g.ai_summary }}</p>{% endif %}
</div>

{% if group %}
<div class="card">
  <strong>Recurring issue</strong>
  <p>This is part of <strong>{{ group.report_count }}</strong> report(s) from
     {{ group.reporter_count }} faculty for the same location and category.
     The admin is handling it as one issue.</p>
</div>
{% endif %}

{% if g.responsible_unit %}
<div class="card"><strong>Assigned to:</strong> {{ g.responsible_unit }}
  {% if g.assignee %}({{ g.assignee }}){% endif %}
  {% if g.due_at %}<br><span class="muted">Due by {{ g.due_at | int }}</span>{% endif %}
</div>
{% endif %}

<h3>Progress</h3>
<ul class="timeline">
{% for s in steps %}
  <li class="{{ 'done' if s.done or s.current }}">{{ s.label }}{% if s.current %} &larr; now{% endif %}</li>
{% endfor %}
</ul>

<h3>Activity</h3>
<ul class="timeline">
{% for e in timeline %}
  <li class="done">{{ e.event_type.replace('_',' ') }}
    {% if e.to_value %}&rarr; {{ e.to_value }}{% endif %}
    {% if e.note %}<br><span class="muted">{{ e.note }}</span>{% endif %}
  </li>
{% endfor %}
</ul>

{% for e in evidence if e.kind != 'report' %}
<div class="card"><strong>{{ e.kind.replace('_',' ') }}</strong>
  {% if e.note %}<p>{{ e.note }}</p>{% endif %}
  <img class="evidence" src="/photo/{{ e.id }}" alt="{{ e.kind }}">
</div>
{% endfor %}
{% endblock %}
```

- [ ] **Step 4: Add to `tests/test_faculty_routes.py`**

```python
def test_my_reports_data_scoped_to_reporter(client):
    _login(client, "prof.rao", "1234")
    client.post("/report", json={
        "description": "Projector will not turn on in this classroom at all",
        "location_type": "academics_block", "block_no": "Block A", "floor": "1st Floor",
        "room": "101", "photo_b64": "aGVsbG8=", "photo_mime": "image/jpeg"})
    data = client.get("/my-reports/data").get_json()
    assert len(data["grievances"]) == 1
    code = data["grievances"][0]["code"]

    # a different faculty cannot open it
    other = client.application.test_client()
    other.post("/login", data={"username": "dr.iyer", "pin": "1234"})
    assert other.get(f"/grievance/{code}").status_code == 403


def test_detail_shows_timeline(client):
    _login(client, "prof.khan", "1234")
    out = client.post("/report", json={
        "description": "The wall has a large crack near the window in this room",
        "location_type": "academics_block", "block_no": "Block C", "floor": "Ground Floor",
        "room": "12", "photo_b64": "aGVsbG8=", "photo_mime": "image/jpeg"}).get_json()
    r = client.get(f"/grievance/{out['code']}")
    assert r.status_code == 200
    assert b"Reported" in r.data and b"Progress" in r.data
```

- [ ] **Step 5: Run** — `pytest tests/test_faculty_routes.py -q` → PASS.

---

### Task 9: PWA — manifest, service worker, icons

**Files:**
- Create: `scripts/make_icons.py`, `static/manifest.webmanifest`, `static/service-worker.js`, `static/icons/icon-192.png`, `static/icons/icon-512.png`
- (base template already wired in Task 6)

**Interfaces:** static files only.

- [ ] **Step 1: Write `scripts/make_icons.py`** (pure-Python solid-navy PNG — no PIL)

```python
"""Generate flat GL-Bajaj-navy PWA icons without Pillow. Run once."""
import struct
import zlib
from pathlib import Path

NAVY = (11, 42, 91)  # #0b2a5b


def _png(size: int, rgb) -> bytes:
    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    row = bytes((0,)) + bytes(rgb) * size          # filter byte + RGB pixels
    raw = row * size
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)  # 8-bit RGB
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


out = Path(__file__).resolve().parent.parent / "static" / "icons"
out.mkdir(parents=True, exist_ok=True)
for s in (192, 512):
    (out / f"icon-{s}.png").write_bytes(_png(s, NAVY))
    print("wrote", out / f"icon-{s}.png")
```

- [ ] **Step 2: Run it** — `python scripts/make_icons.py`
Expected: writes `static/icons/icon-192.png` and `icon-512.png`. Verify: `python -c "import struct; d=open('static/icons/icon-192.png','rb').read(); assert d[:8]==b'\x89PNG\r\n\x1a\n'; print(len(d),'bytes ok')"`

- [ ] **Step 3: Write `static/manifest.webmanifest`**

```json
{
  "name": "UniPulse - GL Bajaj",
  "short_name": "UniPulse",
  "description": "Report and track campus infrastructure issues at GL Bajaj.",
  "start_url": "/",
  "scope": "/",
  "display": "standalone",
  "background_color": "#f6f7f9",
  "theme_color": "#0b2a5b",
  "icons": [
    { "src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable" },
    { "src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable" }
  ]
}
```

- [ ] **Step 4: Write `static/service-worker.js`**

```javascript
const CACHE = "unipulse-shell-v1";
const SHELL = ["/", "/report", "/my-reports", "/notices",
               "/static/css/app.css", "/static/js/report.js",
               "/static/icons/icon-192.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) =>
    Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
  ).then(() => self.clients.claim()));
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  // network-first for data/API, cache-first for the static shell
  if (url.pathname.endsWith("/data") || url.pathname.startsWith("/report/")
      || url.pathname.startsWith("/photo/")) {
    e.respondWith(fetch(req).catch(() => caches.match(req)));
    return;
  }
  e.respondWith(caches.match(req).then((hit) => hit || fetch(req).then((res) => {
    const copy = res.clone();
    caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
    return res;
  }).catch(() => caches.match("/"))));
});
```

- [ ] **Step 5: Add PWA smoke test to `tests/test_faculty_routes.py`**

```python
def test_manifest_and_sw_served(client):
    m = client.get("/static/manifest.webmanifest")
    assert m.status_code == 200
    assert b"UniPulse" in m.data
    sw = client.get("/static/service-worker.js")
    assert sw.status_code == 200
    icon = client.get("/static/icons/icon-192.png")
    assert icon.status_code == 200 and icon.data[:8] == b"\x89PNG\r\n\x1a\n"


def test_base_page_links_manifest(client):
    client.post("/login", data={"username": "prof.rao", "pin": "1234"})
    r = client.get("/")
    assert b"manifest.webmanifest" in r.data
    assert b"serviceWorker" in r.data
```

- [ ] **Step 6: Run** — `pytest tests/test_faculty_routes.py -q` → PASS.

---

### Task 10: Full green + wrap-up

**Files:**
- Modify: `requirements.txt` (no change needed — `requests` already present; confirm)
- Modify: `docs/superpowers/plans/2026-08-30-phaseB-faculty-pwa.md` (tick boxes)

- [ ] **Step 1: Full suite** — `pytest -q` from `unipulse-campus/`. Expected: all pass (Phase 0/A's 50 + Phase B's ~26).

- [ ] **Step 2: Compile check** — `python -m compileall -q app.py wsgi.py config.py db domain services blueprints ai` → exit 0.

- [ ] **Step 3: End-to-end manual check**

```bash
python -c "
from app import create_app
c = create_app().test_client()
c.post('/login', data={'username':'prof.rao','pin':'1234'})
a = c.post('/report/analyze', json={'description':'Wifi and the projector are both down in this classroom'}).get_json()
print('analyze:', a['category'], '|', a['ai_summary'][:50])
s = c.post('/report', json={'description':'Wifi and the projector are both down in this classroom',
  'location_type':'academics_block','block_no':'Block B','floor':'3rd Floor','room':'305',
  'photo_b64':'aGVsbG8=','photo_mime':'image/jpeg'}).get_json()
print('submitted:', s['code'])
print('my-reports:', len(c.get('/my-reports/data').get_json()['grievances']))
d = c.get('/grievance/'+s['code']); print('detail:', d.status_code)
"
```
Expected: `analyze: IT / Network | ...`; `submitted: GLB-CAMP-00001`; `my-reports: 1`; `detail: 200`.

- [ ] **Step 4: Update the memory note** (`~/.claude/.../unipulse-campus-fork.md`) — Phase B done, Phase C next.

---

## Self-Review

**Spec coverage (Phase B scope):**
- §8 pipeline (validate → dup guard → classify → recurring → insert + evidence + timeline) → Task 5, order matches. ✅
- §9 priority formula → Task 3 `priority_score`, all five factors + clamp, tested. ✅
- Faculty screens: home / report wizard / analyze / my-reports / detail / notices → Tasks 6-8. ✅
- Photo capture + campus location picker (Academics drill-down, Outer Area sub-zone) → Task 7 `report.js`. ✅
- AI summary shown before submission → Task 7 step 4 (`/report/analyze` + wizard step 4). ✅
- Unique `GLB-CAMP-#####` on submit → Task 5 (uses Phase A `grievances.next_code`). ✅
- Status + timeline view → Task 8 detail (`steps` + `timeline`). ✅
- Recurring note to faculty ("part of N reports") → Task 5 return + Task 7 done-box + Task 8 detail. ✅
- Campus notices → Task 6. ✅
- Installable PWA (manifest + SW) → Task 9. ✅
- Groq + keyword fallback, runs offline → Tasks 2-3, tests force fallback. ✅
- `services/validation_service.py` recreated → Task 1. ✅
- Deferred (correctly not here): email notifications (E), admin portal (C), priority *recompute hooks* + Pulse/Gap (D), voice input (P2), offline submit queue / Web Push (deferred). ✅

**Placeholder scan:** none. Every code + test step has full content.

**Type consistency:**
- `classification_service.classify(...)` → `{category, severity, ai_summary, confidence, spam_flag, source}` — consumed identically in `grievance_service.submit` (Task 5) and `/report/analyze` (Task 7). ✅
- `duplicate_service.find_recurring(label, category, reporter_id, now=None)` → `{same_reporter_recent, candidates, match}` — consumed in Task 5. ✅
- `grievance_service.submit(sub)` → `{code, grievance_id, category, recurring, spam_flag}`; `SubmissionError.errors` — consumed in Task 7 route + tests. ✅
- `_uid()` / `_TYPE_NAMES` / `bp` defined once in `blueprints/faculty/__init__.py`, referenced across Tasks 6-8 (same module, appended). ✅
- `grievances.find_recurring_candidates(location_label, category, since_ts)` — Phase A signature, used in `duplicate_service` (Task 4). ✅
- `evidence.add(gid, kind, *, image_url, thumbnail_url, uploaded_by)` and `evidence.list_for` — Phase A signatures, used in Task 5/6. ✅
- `recurring.create(location_label, category, title, primary_grievance_id, first_ts)` / `.bump(id, *, last_ts, add_reporter)` / `.find_active` / `.get` — Phase A signatures, used in Task 5. ✅
- `storage_service.upload_image(image_b64, mime, issue_id=None) -> str` — existing signature; Task 5 calls it with two positional args. ✅
- `build_location_label(location_type, block_no, floor, room, sub_zone, *, type_names)` — Phase A signature; Task 7 route passes positionally + `type_names=`. ✅

No issues found.
