# UniPulse — Phase E (Notifications, Analytics, PWA polish, Demo data) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Finish the MVP: email the reporter on status changes and the admin on new
high-priority grievances (Resend); an admin analytics page + CSV export; a
proper offline PWA experience + install prompt; a light accessibility pass; and a
demo-data script that seeds a realistic campus (including the MVP §18 recurring
"Room 204 projector" scenario) for demos.

**Architecture:** New `services/notification_service.py` (Resend REST via `requests`,
degrades to a no-op without `RESEND_API_KEY`) called from `grievance_service`.
`intelligence_service` gains `analytics()`. `admin` blueprint gains
`/admin/analytics` (+ `.csv`). `faculty` blueprint gains `/offline`. New
`scripts/seed_demo.py` with a testable `build()`.

**Tech Stack:** Python 3.12, Flask 3, `requests`, `csv` (stdlib), pytest 9. No new deps.

**Spec:** `docs/superpowers/specs/2026-08-30-unipulse-campus-design.md` (§12 Phase E).
Builds on Phases 0/A/B/C/D (done, 119 tests passing).

## Global Constraints

- Product **UniPulse** / **GL Bajaj**. No new pip deps. Timestamps epoch floats.
- Notifications must **never** break a request — every call site wrapped so a
  failure is logged and swallowed. Without `RESEND_API_KEY` every function is a
  silent no-op returning `{"sent": False, "reason": "not_configured"}`.
- `HIGH_PRIORITY_ALERT = 60` (priority score at/above which — or severity `high` —
  a new grievance alerts the admin).
- Tests run in-memory; `RESEND_API_KEY` unset → notification functions no-op.
- CSV export is admin-only (`@require_permission(ANALYTICS_VIEW)`).
- `/offline` is the ONLY faculty route reachable without login.
- No commits.

---

## File Structure

**Created:**
- `services/notification_service.py`
- `templates/admin/analytics.html`
- `templates/faculty/offline.html`
- `scripts/seed_demo.py`
- `tests/test_notifications.py`, `tests/test_analytics.py`, `tests/test_pwa_offline.py`, `tests/test_seed_demo.py`

**Modified:**
- `config.py` — `RESEND_FROM`, `ADMIN_ALERT_EMAIL`
- `domain/constants.py` — `HIGH_PRIORITY_ALERT = 60`
- `services/grievance_service.py` — call notifications from `submit` + `transition`
- `services/intelligence_service.py` — add `analytics()`
- `blueprints/admin/__init__.py` — `/admin/analytics` + `/admin/analytics.csv`
- `templates/base_admin.html` — add Analytics nav link
- `blueprints/faculty/__init__.py` — `/offline` route + skip-login exemption
- `static/service-worker.js` — navigation-fallback to `/offline`
- `templates/base_faculty.html` — install-prompt button + a11y attrs
- `static/css/app.css` — `:focus-visible` outline

---

### Task 1: `config.py` + constant

**Files:** Modify `config.py`, `domain/constants.py`

- [ ] **Step 1:** In `config.py`, after `GROQ_MODEL_VISION`:

```python
    RESEND_FROM       = os.environ.get("RESEND_FROM", "UniPulse <onboarding@resend.dev>").strip()
    ADMIN_ALERT_EMAIL = (os.environ.get("ADMIN_ALERT_EMAIL")
                         or os.environ.get("DEMO_RECIPIENT_EMAIL") or "").strip()
```

- [ ] **Step 2:** In `domain/constants.py`, after `GAP_THRESHOLD = 4`:

```python
HIGH_PRIORITY_ALERT = 60   # new grievance at/above this priority (or severity high) alerts the admin
```

- [ ] **Step 3:** `python -c "from config import Config; from domain.constants import HIGH_PRIORITY_ALERT; print(Config.RESEND_FROM, HIGH_PRIORITY_ALERT)"` → prints the from-address and `60`.

---

### Task 2: `services/notification_service.py`

**Files:** Create `services/notification_service.py`
**Test:** `tests/test_notifications.py`

**Interfaces:**
- `notification_service`:
  - `is_available() -> bool` — `bool(Config.RESEND_API_KEY)`
  - `_deliver(to: str, subject: str, html: str) -> dict` — the single HTTP call (POST `https://api.resend.com/emails`). Tests monkeypatch this.
  - `notify_status_change(grievance: dict, new_status: str, reporter_contact: str | None) -> dict` — emails the reporter; no-op if no contact or not available.
  - `notify_new_high_priority(grievance: dict) -> dict` — emails `Config.ADMIN_ALERT_EMAIL`; no-op if empty or not available.
  - All return `{"sent": bool, "reason": str}` and never raise.

- [ ] **Step 1:** Write `tests/test_notifications.py`

```python
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
```

- [ ] **Step 2:** Run — fails.

- [ ] **Step 3:** Write `services/notification_service.py`

```python
"""Resend email notifications. Degrades to a silent no-op without RESEND_API_KEY."""
from __future__ import annotations

import requests

from config import Config
from domain.constants import GLB

_URL = "https://api.resend.com/emails"
_TIMEOUT = 10
_NOOP = {"sent": False, "reason": "not_configured"}


def is_available() -> bool:
    return bool(Config.RESEND_API_KEY)


def _deliver(to: str, subject: str, html: str) -> dict:
    resp = requests.post(
        _URL, timeout=_TIMEOUT,
        headers={"Authorization": f"Bearer {Config.RESEND_API_KEY}",
                 "Content-Type": "application/json"},
        json={"from": Config.RESEND_FROM, "to": [to], "subject": subject, "html": html},
    )
    resp.raise_for_status()
    return {"sent": True, "reason": "ok"}


def _safe(to, subject, html) -> dict:
    if not is_available():
        return dict(_NOOP)
    if not to:
        return {"sent": False, "reason": "no_recipient"}
    try:
        return _deliver(to, subject, html)
    except Exception as e:  # noqa: BLE001
        print(f"[notification_service] delivery failed: {type(e).__name__}: {e}")
        return {"sent": False, "reason": f"{type(e).__name__}: {e}"}


def notify_status_change(grievance: dict, new_status: str,
                         reporter_contact: str | None) -> dict:
    code = grievance.get("code", "your grievance")
    label = grievance.get("location_label", "")
    pretty = new_status.replace("_", " ")
    html = (f"<p>Your report <strong>{code}</strong> ({label}) is now "
            f"<strong>{pretty}</strong>.</p>"
            f"<p>Track it in {GLB['product']}.</p>")
    return _safe(reporter_contact, f"[{GLB['product']}] {code} is now {pretty}", html)


def notify_new_high_priority(grievance: dict) -> dict:
    code = grievance.get("code", "?")
    html = (f"<p>New high-priority grievance <strong>{code}</strong>.</p>"
            f"<p>Category: {grievance.get('category') or 'unclassified'} &middot; "
            f"priority {grievance.get('priority_score', 0)} &middot; "
            f"{grievance.get('location_label', '')}</p>")
    return _safe(Config.ADMIN_ALERT_EMAIL,
                 f"[{GLB['product']}] High-priority: {code}", html)
```

- [ ] **Step 4:** Run `pytest tests/test_notifications.py -q` → PASS (5).

---

### Task 3: Wire notifications into `grievance_service`

**Files:** Modify `services/grievance_service.py`
**Test:** `tests/test_notifications.py` (add integration)

**Interfaces:** no signature changes — `submit()` and `transition()` gain best-effort notification calls.

- [ ] **Step 1:** In `services/grievance_service.py`, add to the imports:

```python
from domain.constants import HIGH_PRIORITY_ALERT
from services import notification_service
```
(merge `HIGH_PRIORITY_ALERT` into the existing `from domain.constants import (...)` line.)

- [ ] **Step 2:** In `submit()`, immediately before the final `return {...}`:

```python
    try:
        if priority >= HIGH_PRIORITY_ALERT or cls["severity"] == "high":
            notification_service.notify_new_high_priority(grievances.get_by_id(g["id"]))
    except Exception as e:  # noqa: BLE001
        print(f"[grievance_service] high-priority alert failed: {e}")
```

- [ ] **Step 3:** In `transition()`, immediately before `return grievances.get_by_id(gid)`:

```python
    try:
        updated = grievances.get_by_id(gid)
        reporter = users.get_by_id(updated["reporter_id"]) if updated["reporter_id"] else None
        notification_service.notify_status_change(
            updated, to_status, reporter.get("contact") if reporter else None)
    except Exception as e:  # noqa: BLE001
        print(f"[grievance_service] status email failed: {e}")
```

- [ ] **Step 4:** Add to `tests/test_notifications.py`

```python
def test_pipeline_triggers_alert_and_status_email(monkeypatch, memstore):
    from db import users
    from services import grievance_service as gs

    calls = []
    monkeypatch.setattr("services.notification_service.notify_new_high_priority",
                        lambda g: calls.append(("alert", g["code"])) or {"sent": True})
    monkeypatch.setattr("services.notification_service.notify_status_change",
                        lambda g, s, c: calls.append(("status", s)) or {"sent": True})

    u = users.create("prof.x", "Prof X", "reporter",
                     __import__("services.auth_service", fromlist=["hash_pin"]).hash_pin("1"),
                     contact="profx@glbitm.ac.in")
    out = gs.submit({
        "reporter_id": u["id"],
        "description": "Exposed live wire sparking near the door, very dangerous",
        "location_type": "academics_block", "block_no": "Block B", "floor": "2nd Floor",
        "room": "204", "location_label": "Academics Block > Block B > 2nd Floor > Room 204",
        "photo_b64": "aGVsbG8=", "photo_mime": "image/jpeg",
    })
    assert ("alert", out["code"]) in calls          # high severity -> admin alert
    g = gs.grievances.get_by_code(out["code"])
    gs.transition(g["id"], "verified", actor="admin", actor_role="admin")
    assert ("status", "verified") in calls
```

- [ ] **Step 5:** Run `pytest tests/test_notifications.py -q` → PASS (6).

---

### Task 4: `intelligence_service.analytics()`

**Files:** Modify `services/intelligence_service.py`
**Test:** `tests/test_analytics.py`

**Interfaces:**
- `analytics() -> dict`:
  ```
  {
    "total": int,
    "resolution_rate": float,          # (resolved+admin_verified+closed) / total, %, 1dp
    "avg_resolution_hours": float | None,   # mean (resolved_at - created_at)/3600 over rows with both, 1dp
    "sla_breach_rate": float,          # breached / total, %, 1dp
    "by_category": {cat: count},       # every category present, 0 if none
    "by_status": {status: count},      # every status
    "by_unit": {unit: {"total": int, "resolved": int}},  # only units with >=1
    "by_location_type": {type_name: count},
  }
  ```

- [ ] **Step 1:** Write `tests/test_analytics.py`

```python
import time

from db import grievances, users
from services import intelligence_service as si
from services.auth_service import hash_pin


def _g(memstore, **kw):
    u = users.create(f"u{time.time_ns()}", "U", "reporter", hash_pin("1"))
    base = dict(reporter_id=u["id"], reporter_name="U", title="t",
                description="broken thing here now", location_type="hostels",
                location_label="Hostels", category="Electric", severity="medium",
                status="reported", priority_score=10, created_at=time.time())
    base.update(kw)
    return grievances.insert(**base)


def test_analytics_empty(memstore):
    a = si.analytics()
    assert a["total"] == 0
    assert a["resolution_rate"] == 0.0
    assert a["avg_resolution_hours"] is None
    assert set(a["by_category"]) == set(si.CATEGORIES) if hasattr(si, "CATEGORIES") else True


def test_analytics_rates(memstore):
    _g(memstore, status="reported")
    r = _g(memstore, status="closed", created_at=time.time() - 10 * 3600)
    grievances.update(r["id"], resolved_at=time.time() - 4 * 3600)
    b = _g(memstore, status="assigned")
    grievances.update(b["id"], due_at=time.time() - 3600)   # breached
    a = si.analytics()
    assert a["total"] == 3
    assert a["resolution_rate"] == round(1 / 3 * 100, 1)
    assert a["sla_breach_rate"] == round(1 / 3 * 100, 1)
    assert a["avg_resolution_hours"] == 6.0
    assert a["by_category"]["Electric"] == 3
    assert a["by_status"]["closed"] == 1


def test_analytics_by_unit(memstore):
    g = _g(memstore, status="resolved", responsible_unit="Infrastructure")
    _g(memstore, status="assigned", responsible_unit="Infrastructure")
    a = si.analytics()
    assert a["by_unit"]["Infrastructure"] == {"total": 2, "resolved": 1}
```

- [ ] **Step 2:** Add to `services/intelligence_service.py` (import `CATEGORIES`, `STATUSES` at top; they may already be partly imported — ensure both present):

```python
def analytics() -> dict:
    rows = _all()
    now = time.time()
    total = len(rows)

    done = [g for g in rows if g["status"] in _DONE]
    breached = sum(1 for g in rows if _is_breached(g, now))

    res_hours = [(g["resolved_at"] - g["created_at"]) / 3600
                 for g in rows
                 if g.get("resolved_at") and g.get("created_at")
                 and g["resolved_at"] >= g["created_at"]]

    by_cat = {c: 0 for c in CATEGORIES}
    for g in rows:
        if g["category"] in by_cat:
            by_cat[g["category"]] += 1

    by_status = {s: 0 for s in STATUSES}
    for g in rows:
        if g["status"] in by_status:
            by_status[g["status"]] += 1

    by_unit: dict = {}
    for g in rows:
        u = g.get("responsible_unit")
        if not u:
            continue
        slot = by_unit.setdefault(u, {"total": 0, "resolved": 0})
        slot["total"] += 1
        if g["status"] in _DONE:
            slot["resolved"] += 1

    by_loc: dict = {}
    for g in rows:
        name = _TYPE_NAMES.get(g["location_type"], g["location_type"] or "Unknown")
        by_loc[name] = by_loc.get(name, 0) + 1

    return {
        "total": total,
        "resolution_rate": round(len(done) / total * 100, 1) if total else 0.0,
        "avg_resolution_hours": round(sum(res_hours) / len(res_hours), 1) if res_hours else None,
        "sla_breach_rate": round(breached / total * 100, 1) if total else 0.0,
        "by_category": by_cat,
        "by_status": by_status,
        "by_unit": by_unit,
        "by_location_type": by_loc,
    }
```

Also ensure the module imports `CATEGORIES` and `STATUSES` from `domain.constants` (add them to the existing import line).

- [ ] **Step 3:** Run `pytest tests/test_analytics.py -q` → PASS (3).

---

### Task 5: `/admin/analytics` page + CSV export

**Files:** Modify `blueprints/admin/__init__.py`, `templates/base_admin.html`; create `templates/admin/analytics.html`
**Test:** `tests/test_analytics.py` (route portion)

**Interfaces:**
- `GET /admin/analytics` (`@require_permission(ANALYTICS_VIEW)`) → `analytics.html`.
- `GET /admin/analytics.csv` (`@require_permission(ANALYTICS_VIEW)`) → `text/csv` attachment, one row per grievance.

- [ ] **Step 1:** Add to `blueprints/admin/__init__.py`

```python
import csv
import io as _io

from flask import Response


@bp.get("/analytics")
@require_permission(ANALYTICS_VIEW)
def analytics_page():
    return render_template("admin/analytics.html", a=intelligence_service.analytics())


@bp.get("/analytics.csv")
@require_permission(ANALYTICS_VIEW)
def analytics_csv():
    cols = ["code", "category", "severity", "status", "priority_score", "location_label",
            "responsible_unit", "assignee", "created_at", "assigned_at", "due_at",
            "resolved_at", "closed_at", "recurring_group_id", "spam_flag"]
    buf = _io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    for g in grievances.list_query(limit=100000):
        w.writerow([g.get(c) for c in cols])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=unipulse_grievances.csv"})
```

- [ ] **Step 2:** In `templates/base_admin.html`, add to `.adminnav` (after the Gaps link):

```html
    <a href="/admin/analytics" class="{{ 'on' if p == '/admin/analytics' }}">Analytics</a>
```

- [ ] **Step 3:** Write `templates/admin/analytics.html`

```html
{% extends "base_admin.html" %}{% block title %}Analytics{% endblock %}{% block content %}
<h2>Analytics <a class="btn" href="/admin/analytics.csv" style="float:right">Export CSV</a></h2>
<div class="kpi-row">
  <div class="kpi"><b>{{ a.total }}</b>Total grievances</div>
  <div class="kpi"><b>{{ a.resolution_rate }}%</b>Resolution rate</div>
  <div class="kpi"><b>{{ a.avg_resolution_hours if a.avg_resolution_hours is not none else '-' }}</b>Avg hrs to resolve</div>
  <div class="kpi"><b>{{ a.sla_breach_rate }}%</b>SLA breach rate</div>
</div>

<h3>By category</h3>
<table class="grid"><tbody>
{% for c, n in a.by_category.items() %}<tr><td>{{ c }}</td><td>{{ n }}</td></tr>{% endfor %}
</tbody></table>

<h3>By status</h3>
<table class="grid"><tbody>
{% for s, n in a.by_status.items() %}<tr><td>{{ s.replace('_',' ') }}</td><td>{{ n }}</td></tr>{% endfor %}
</tbody></table>

<h3>By responsible unit</h3>
<table class="grid"><thead><tr><th>Unit</th><th>Total</th><th>Resolved</th></tr></thead><tbody>
{% for u, v in a.by_unit.items() %}<tr><td>{{ u }}</td><td>{{ v.total }}</td><td>{{ v.resolved }}</td></tr>
{% else %}<tr><td class="muted" colspan="3">Nothing assigned yet.</td></tr>{% endfor %}
</tbody></table>

<h3>By location type</h3>
<table class="grid"><tbody>
{% for t, n in a.by_location_type.items() %}<tr><td>{{ t }}</td><td>{{ n }}</td></tr>{% endfor %}
</tbody></table>
{% endblock %}
```

- [ ] **Step 4:** Add to `tests/test_analytics.py`

```python
def test_analytics_routes(client):
    client.post("/login", data={"username": "admin", "pin": "0000"})
    assert client.get("/admin/analytics").status_code == 200
    csv_r = client.get("/admin/analytics.csv")
    assert csv_r.status_code == 200
    assert csv_r.mimetype == "text/csv"
    assert b"code,category,severity" in csv_r.data


def test_analytics_blocked_for_faculty(client):
    client.post("/login", data={"username": "prof.rao", "pin": "1234"})
    assert client.get("/admin/analytics").status_code == 403
    assert client.get("/admin/analytics.csv").status_code == 403
```

- [ ] **Step 5:** Run `pytest tests/test_analytics.py -q` → PASS (5).

---

### Task 6: PWA offline page + install prompt + a11y pass

**Files:** Modify `blueprints/faculty/__init__.py`, `static/service-worker.js`, `templates/base_faculty.html`, `static/css/app.css`; create `templates/faculty/offline.html`
**Test:** `tests/test_pwa_offline.py`

**Interfaces:**
- `GET /offline` → `faculty/offline.html`, reachable without login (added to the `_require_login` exemption).

- [ ] **Step 1:** In `blueprints/faculty/__init__.py` `_require_login`:

```python
@bp.before_request
def _require_login():
    if request.path == "/offline":
        return
    if not g.get("current_user"):
        return redirect("/login")
    if g.current_user["role"] == "admin" and request.path == "/":
        return redirect("/admin")
```

and add the route:

```python
@bp.get("/offline")
def offline_page():
    return render_template("faculty/offline.html")
```

- [ ] **Step 2:** Write `templates/faculty/offline.html`

```html
{% extends "base_faculty.html" %}
{% block title %}Offline{% endblock %}
{% block content %}
<h2>You're offline</h2>
<p class="muted">UniPulse needs a connection to submit or refresh reports.
  Reconnect and try again - anything you were typing is still here.</p>
<p><a class="btn" href="/">Retry</a></p>
{% endblock %}
```

- [ ] **Step 3:** Update `static/service-worker.js` — replace the `SHELL` list and the fetch handler's navigation fallback:

```javascript
const CACHE = "unipulse-shell-v2";
const SHELL = ["/", "/report", "/my-reports", "/notices", "/offline",
               "/static/css/app.css", "/static/js/report.js",
               "/static/icons/icon-192.png"];
```

and in the `fetch` handler, change the final `.catch(() => caches.match("/"))` to:

```javascript
  }).catch(() => caches.match(req.mode === "navigate" ? "/offline" : "/"))));
```

- [ ] **Step 4:** In `templates/base_faculty.html`, add an install button + prompt handling to the existing `<script>` block (after the SW registration), and an `aria-label` on the bottom nav:

```html
  <nav class="bottomnav" aria-label="Primary">
```

```html
  <button id="pwa-install" hidden class="btn" style="position:fixed;right:12px;bottom:80px">Install app</button>
  <script>
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("{{ url_for('static', filename='service-worker.js') }}");
    }
    let _deferredPrompt = null;
    window.addEventListener("beforeinstallprompt", (e) => {
      e.preventDefault(); _deferredPrompt = e;
      const b = document.getElementById("pwa-install"); if (b) b.hidden = false;
    });
    const _ib = document.getElementById("pwa-install");
    if (_ib) _ib.addEventListener("click", async () => {
      _ib.hidden = true;
      if (_deferredPrompt) { _deferredPrompt.prompt(); _deferredPrompt = null; }
    });
  </script>
```
(remove the old standalone SW-registration `<script>` so it isn't duplicated.)

- [ ] **Step 5:** Append to `static/css/app.css`

```css
:focus-visible { outline: 3px solid #1e5fbf; outline-offset: 2px; }
a, button { -webkit-tap-highlight-color: transparent; }
```

- [ ] **Step 6:** Add `aria-label`s where a control has no visible text — in `templates/faculty/report.html` give the file input `aria-label="Photo of the problem"` and in `base_admin.html` add `aria-label="Admin sections"` to `.adminnav`.

- [ ] **Step 7:** Write `tests/test_pwa_offline.py`

```python
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
```

- [ ] **Step 8:** Run `pytest tests/test_pwa_offline.py -q` → PASS (3).

---

### Task 7: `scripts/seed_demo.py`

**Files:** Create `scripts/seed_demo.py`
**Test:** `tests/test_seed_demo.py`

**Interfaces:**
- `seed_demo.build() -> dict` — idempotent; returns `{"grievances": int, "recurring_groups": int, "gaps": int}`. Safe to call against an already-seeded store (skips if `grievances.list_query()` is non-empty).
- Seeds:
  - **MVP §18 scenario:** 4 "projector in Room 204 (Block B, 2nd Floor)" reports from `prof.rao`, `dr.iyer`, `prof.khan`, `prof.sharma` → forms one recurring group; the group's first grievance is carried to `assigned`.
  - **Block B electrical cluster:** 4 "tubelight / switchboard / fan" reports in Block B (different rooms) → triggers a Gap.
  - A plumbing leak in Hostels marked `resolved`+`admin_verified` with `resolution_after` evidence.
  - One overdue `assigned` grievance (past `due_at`).
  - Two `closed` grievances.
- `if __name__ == "__main__":` → `from db import pool; pool.init_db(); print(build())`.

- [ ] **Step 1:** Write `tests/test_seed_demo.py`

```python
from scripts import seed_demo
from services import intelligence_service as si


def test_build_creates_recurring_and_gap(memstore):
    # seed_demo needs the standard accounts
    from db import seeds
    seeds.run()
    out = seed_demo.build()
    assert out["grievances"] >= 10
    assert out["recurring_groups"] >= 1
    assert out["gaps"] >= 1
    # the Room 204 projector recurrence exists
    groups = si.recurring.list_active()
    assert any("204" in g["title"] or "Projector" in g["title"] or "projector" in g["title"].lower()
               for g in groups)


def test_build_is_idempotent(memstore):
    from db import seeds
    seeds.run()
    first = seed_demo.build()
    second = seed_demo.build()
    assert second == first
```

- [ ] **Step 2:** Write `scripts/seed_demo.py`

```python
"""Realistic demo campus data for UniPulse. Idempotent. Run: python scripts/seed_demo.py"""
from __future__ import annotations

from db import grievances, users
from services import grievance_service as gs
from services import intelligence_service as si

_B204 = dict(location_type="academics_block", block_no="Block B", floor="2nd Floor",
             room="204", sub_zone=None,
             location_label="Academics Block > Block B > 2nd Floor > Room 204",
             photo_b64="aGVsbG8=", photo_mime="image/jpeg")


def _sub(uname, description, **over):
    u = users.get_by_username(uname)
    base = dict(reporter_id=u["id"], description=description, **_B204)
    base.update(over)
    return gs.submit(base)


def _blockb_room(n, floor="1st Floor"):
    return dict(location_type="academics_block", block_no="Block B", floor=floor,
                room=str(n), sub_zone=None,
                location_label=f"Academics Block > Block B > {floor} > Room {n}",
                photo_b64="aGVsbG8=", photo_mime="image/jpeg")


def build() -> dict:
    if grievances.list_query(limit=1):
        # already seeded
        return {"grievances": len(grievances.list_query(limit=100000)),
                "recurring_groups": len(si.recurring.list_active()),
                "gaps": len(si.gaps())}

    faculty = ["prof.rao", "dr.iyer", "prof.khan", "prof.sharma"]

    # 1. MVP §18 - Room 204 projector, 4 faculty
    proj_desc = ["The projector in Room 204 will not switch on again",
                 "Projector 204 is completely dead, no signal to the screen",
                 "Room 204 projector not working - third time this month",
                 "The projector and HDMI in 204 are down again"]
    first_code = None
    for uname, d in zip(faculty, proj_desc):
        out = _sub(uname, d)
        first_code = first_code or out["code"]
    g1 = grievances.get_by_code(first_code)
    gs.transition(g1["id"], "verified", actor="admin", actor_role="admin")
    gs.assign(g1["id"], unit="Lab", assignee="AV support", actor="admin")

    # 2. Block B electrical cluster -> a Gap
    cluster = [("prof.rao", "The tubelight keeps flickering in this room", 101),
               ("dr.iyer", "Switchboard is sparking near the entrance", 105),
               ("prof.khan", "Ceiling fan is not working at all here", 108),
               ("prof.sharma", "Half the lights in this room are dead", 112)]
    for uname, d, room in cluster:
        u = users.get_by_username(uname)
        gs.submit(dict(reporter_id=u["id"], description=d, **_blockb_room(room)))

    # 3. Hostel plumbing - fully closed with evidence
    u = users.get_by_username("prof.khan")
    p = gs.submit(dict(reporter_id=u["id"],
                       description="Water is leaking from the pipe under the basin in the hostel washroom",
                       location_type="hostels", sub_zone=None, location_label="Hostels",
                       block_no=None, floor=None, room=None,
                       photo_b64="aGVsbG8=", photo_mime="image/jpeg"))
    pg = grievances.get_by_code(p["code"])
    gs.transition(pg["id"], "verified", actor="admin", actor_role="admin")
    gs.assign(pg["id"], unit="Infrastructure", assignee="Plumbing team", actor="admin")
    gs.transition(pg["id"], "in_progress", actor="admin", actor_role="admin")
    gs.add_resolution_evidence(pg["id"], kind="resolution_after", image_b64="aGk=",
                               mime="image/png", note="Replaced the P-trap and tightened the joint",
                               actor="admin")
    gs.transition(pg["id"], "resolved", actor="admin", actor_role="admin")
    gs.transition(pg["id"], "admin_verified", actor="admin", actor_role="admin")

    # 4. one overdue assigned grievance
    u = users.get_by_username("prof.sharma")
    o = gs.submit(dict(reporter_id=u["id"],
                       description="The AC in the mess hall has stopped cooling completely",
                       location_type="mess_canteen", sub_zone=None, block_no=None,
                       floor=None, room=None, location_label="Mess / Canteen",
                       photo_b64="aGVsbG8=", photo_mime="image/jpeg"))
    og = grievances.get_by_code(o["code"])
    gs.transition(og["id"], "verified", actor="admin", actor_role="admin")
    gs.assign(og["id"], unit="Mess", assignee="Facilities", actor="admin",
              due_at=1.0)   # already overdue

    return {"grievances": len(grievances.list_query(limit=100000)),
            "recurring_groups": len(si.recurring.list_active()),
            "gaps": len(si.gaps())}


if __name__ == "__main__":
    from db import pool, seeds
    pool.init_db()
    seeds.run()
    print(build())
```

- [ ] **Step 3:** Create `scripts/__init__.py` (empty) so `from scripts import seed_demo` works in tests.

- [ ] **Step 4:** Run `pytest tests/test_seed_demo.py -q` → PASS (2).

---

### Task 8: Full green + final wrap-up

- [ ] **Step 1:** Clean + full suite:

```bash
cd "C:/Users/rocky/OneDrive/Desktop/unipulse/unipulse-campus"
rm -rf __pycache__ */__pycache__ */*/__pycache__ .pytest_cache tests/__pycache__ scripts/__pycache__
python -m pytest -q
```
Expected: all pass (119 + ~24).

- [ ] **Step 2:** Compile:

```bash
python -m compileall -q app.py wsgi.py config.py db domain services blueprints ai scripts
```
Expected: exit 0.

- [ ] **Step 3:** Full demo walkthrough:

```bash
python -c "
from app import create_app
from db import pool, seeds
from scripts import seed_demo
app = create_app()
print('seed_demo:', seed_demo.build())
ad = app.test_client(); ad.post('/login', data={'username':'admin','pin':'0000'})
for path in ['/admin','/admin/grievances/data','/admin/recurring','/admin/pulse',
             '/admin/gaps','/admin/analytics','/admin/analytics.csv','/admin/audit']:
    print(path, ad.get(path).status_code)
fac = app.test_client(); fac.post('/login', data={'username':'prof.rao','pin':'1234'})
print('/ ', fac.get('/').status_code, '| /my-reports/data',
      len(fac.get('/my-reports/data').get_json()['grievances']))
print('/offline', app.test_client().get('/offline').status_code)
" 2>&1 | grep -v "storage_service\|\[db\]"
```
Expected: `seed_demo` reports `grievances >= 12, recurring_groups >= 1, gaps >= 1`; every admin path 200; `/offline` 200.

- [ ] **Step 4:** Write a `README.md` at the project root summarising how to run it (dev: `python app.py`; demo data: `python scripts/seed_demo.py`; tests: `pytest`; env: copy `.env.example`).

- [ ] **Step 5:** Update the memory note — all phases (0-E) complete; MVP done.

---

## Self-Review

**Spec coverage (Phase E):**
- Email notifications (Resend) on status change + new high-severity/priority → Tasks 2, 3. ✅
- `/admin/analytics` + exportable CSV → Tasks 4, 5. ✅
- Installable PWA polish (offline page, install prompt) + a11y pass → Task 6. ✅
- Demo data incl. MVP §18 "Room 204" recurring scenario → Task 7. ✅
- Everything degrades without `RESEND_API_KEY` (no-op) — Task 2. ✅

**Placeholder scan:** none — every code + test step complete.

**Type consistency:**
- `notification_service.notify_status_change(grievance, new_status, reporter_contact)` / `notify_new_high_priority(grievance)` → `{"sent": bool, "reason": str}`; `_deliver(to, subject, html)` is the monkeypatch seam — signatures consistent Tasks 2, 3, and both tests. ✅
- `grievance_service.submit` / `transition` gain best-effort calls only — no signature change, existing callers (Phase B/C routes + tests) unaffected. ✅
- `intelligence_service.analytics()` dict keys (`total, resolution_rate, avg_resolution_hours, sla_breach_rate, by_category, by_status, by_unit, by_location_type`) — produced Task 4, consumed by `analytics.html` (Task 5) with matching keys, tested Task 4/5. ✅ Uses `_all()`, `_is_breached`, `_DONE`, `_TYPE_NAMES` already defined in the module (Phase C/D).
- `intelligence_service` needs `CATEGORIES` + `STATUSES` imported — Task 4 step 2 note ensures both are on the import line (currently it imports `GAP_THRESHOLD, LOCATION_TYPES, PULSE_DOMAINS`). ✅
- `seed_demo.build()` → `{"grievances", "recurring_groups", "gaps"}` — consumed by its own test + the Task 8 walkthrough; uses `grievance_service.submit/transition/assign/add_resolution_evidence` (Phase B/C signatures) and `intelligence_service.recurring` / `.gaps` (module attr + fn). ✅
- SW cache bumped `v1 → v2` so the new shell (incl. `/offline`) is picked up. ✅
- `/offline` exemption added before the login check in `_require_login` (Task 6 step 1) — the only unauthenticated faculty route, per Global Constraints. ✅

No issues found.
