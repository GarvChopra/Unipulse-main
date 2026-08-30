# Faculty Mobile UI Redesign — Implementation Plan

> **For agentic workers:** execute with superpowers:executing-plans. Backend/logic
> steps carry full code + tests; template/CSS/JS steps carry the full asset content.
> Checkbox (`- [ ]`) steps.

**Goal:** Restyle the faculty PWA to the `ui-mockups.png` collage (restrained
palette) and add the features the mockup implies: in-app camera, faculty-picked
priority, `noticed_at` + `affects_academics` fields, campus-health on home,
profile screen, notification-bell dot, remember-me, 300-char description.

**Architecture:** Pure CSS/template/JS restyle over the existing routes + a small
set of backend deltas (2 columns, severity-from-form, priority tweak, 2 routes).
No route renames, no JSON-shape changes → existing tests stay green with additive
edits only.

**Spec:** `docs/superpowers/specs/2026-08-30-faculty-mobile-ui.md`.

## Global Constraints

- White page backgrounds. One brown accent `--brand #7a3b2e`. Status colours only inside chips.
- Category is AI-only — no category field on the report form.
- Priority pick (Low/Medium/High) → grievance `severity`.
- Codes stay `GLB-CAMP-#####`. Description max 300.
- Preserve every element `id`, form field `name`, route path, and JSON key the JS/tests use.
- Brand assets are SVG placeholders at `static/img/glb-logo.svg` + `static/img/campus-hero.svg`.
- No commits.

---

## Phase E1 — Design system + backend deltas

### Task 1: `static/css/app.css` — full rebuild

**Files:** replace `static/css/app.css`

- [ ] **Step 1:** Replace the entire file with:

```css
/* ============ UniPulse — tokens ============ */
:root{
  --bg:#ffffff; --surface:#ffffff; --ink:#2b2320; --muted:#8b817a; --faint:#b8afa7;
  --line:#ebe5df; --line-strong:#ddd4cc;
  --brand:#7a3b2e; --brand-ink:#ffffff; --brand-soft:#f6efeb;
  --ok:#2e7d5b; --warn:#b0791f; --alert:#b23b3b;
  --ok-bg:#eaf3ee; --warn-bg:#f7efe0; --alert-bg:#f6e9e9;
  --r:14px; --r-sm:10px; --r-lg:20px;
  --shadow:0 1px 2px rgba(43,35,32,.05), 0 6px 20px rgba(43,35,32,.06);
  --nav-h:60px;
}
*{box-sizing:border-box}
html,body{margin:0}
body{background:var(--bg);color:var(--ink);
  font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Inter,sans-serif;
  -webkit-font-smoothing:antialiased}
a{color:var(--brand);text-decoration:none}
h1,h2,h3{margin:.2em 0 .5em;line-height:1.25}
h2{font-size:20px} h3{font-size:16px}
.muted{color:var(--muted)} .tiny{font-size:12.5px}

/* ============ layout ============ */
.app-header{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:10px;
  background:#fff;border-bottom:1px solid var(--line);padding:10px 14px;min-height:54px}
.app-header .logo{height:26px;width:auto}
.app-header .h-title{font-weight:700;font-size:15px;flex:1;letter-spacing:.2px}
.app-header .h-title small{display:block;font-weight:500;color:var(--muted);font-size:11.5px;letter-spacing:0}
.icon-btn{position:relative;width:36px;height:36px;border:0;background:transparent;color:var(--ink);
  display:grid;place-items:center;border-radius:50%}
.icon-btn:active{background:var(--brand-soft)}
.icon-btn .dot{position:absolute;top:7px;right:7px;width:8px;height:8px;border-radius:50%;
  background:var(--alert);border:2px solid #fff}
.avatar{width:32px;height:32px;border-radius:50%;background:var(--brand-soft);color:var(--brand);
  display:grid;place-items:center;font-weight:700;font-size:13px}
.app-main{padding:16px 14px calc(var(--nav-h) + 20px)}
.screen-title{display:flex;align-items:center;gap:10px;margin:2px 0 14px}
.screen-title .back{width:34px;height:34px;border:1px solid var(--line);border-radius:50%;
  background:#fff;display:grid;place-items:center;color:var(--ink)}

/* ============ cards ============ */
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);
  padding:16px;box-shadow:var(--shadow);margin:12px 0}
.card.tight{padding:13px}
.card-row{display:flex;justify-content:space-between;align-items:center;gap:10px}
.list-card{display:block;color:inherit}
.list-card:active{border-color:var(--line-strong)}

/* primary action */
.action-card{background:var(--brand);color:var(--brand-ink);border:0;border-radius:var(--r);
  padding:18px;display:flex;align-items:center;justify-content:space-between;
  box-shadow:var(--shadow);width:100%;text-align:left}
.action-card b{font-size:17px;display:block}
.action-card span{opacity:.85;font-size:12.5px}
.action-card .arrow{width:34px;height:34px;border-radius:50%;background:rgba(255,255,255,.16);
  display:grid;place-items:center;flex-shrink:0}

/* stat cards */
.stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:12px 0}
.stat{background:#fff;border:1px solid var(--line);border-radius:var(--r);padding:14px}
.stat .n{font-size:22px;font-weight:800}
.stat .l{font-size:12.5px;color:var(--muted)}

/* campus health */
.health-row{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.health{background:#fff;border:1px solid var(--line);border-radius:var(--r-sm);padding:10px;text-align:center}
.health .pct{font-size:18px;font-weight:800;color:var(--brand)}
.health .lbl{font-size:11px;color:var(--muted)}
.health .bar{height:5px;background:var(--brand-soft);border-radius:3px;margin-top:6px;overflow:hidden}
.health .bar>i{display:block;height:100%;background:var(--brand)}

/* ============ chips / badges ============ */
.chip{display:inline-block;padding:3px 10px;border-radius:999px;font-size:11.5px;font-weight:700;
  letter-spacing:.2px}
.chip.reported,.chip.open{background:var(--warn-bg);color:var(--warn)}
.chip.verified,.chip.assigned,.chip.in_progress{background:var(--warn-bg);color:var(--warn)}
.chip.resolved,.chip.admin_verified,.chip.closed{background:var(--ok-bg);color:var(--ok)}
.badge-pri{font-size:11px;font-weight:800;padding:2px 8px;border-radius:6px;text-transform:capitalize}
.badge-pri.high{background:var(--alert-bg);color:var(--alert)}
.badge-pri.medium{background:var(--warn-bg);color:var(--warn)}
.badge-pri.low{background:var(--ok-bg);color:var(--ok)}

/* ============ forms ============ */
label{display:block;font-weight:600;font-size:13px;margin:14px 0 5px}
input,select,textarea{width:100%;font:inherit;color:var(--ink);background:#fff;
  border:1px solid var(--line-strong);border-radius:var(--r-sm);padding:12px 13px}
input:focus,select:focus,textarea:focus{outline:none;border-color:var(--brand);
  box-shadow:0 0 0 3px var(--brand-soft)}
textarea{resize:vertical;min-height:96px}
.counter{text-align:right;font-size:11.5px;color:var(--faint);margin-top:4px}
.check{display:flex;gap:10px;align-items:flex-start;margin-top:14px;font-weight:500}
.check input{width:18px;height:18px;margin-top:2px;flex-shrink:0}

/* priority pills */
.pri-pills{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:6px}
.pri-pills button{border:1px solid var(--line-strong);background:#fff;color:var(--muted);
  border-radius:var(--r-sm);padding:11px 6px;font-weight:700;font-size:13px}
.pri-pills button[aria-pressed="true"]{border-color:var(--brand);color:var(--brand);background:var(--brand-soft)}

/* buttons */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;width:100%;
  background:var(--brand);color:#fff;border:0;border-radius:var(--r-sm);
  padding:14px 18px;font:inherit;font-weight:700;cursor:pointer}
.btn:active{filter:brightness(.94)}
.btn[disabled]{opacity:.55}
.btn.ghost{background:#fff;color:var(--brand);border:1px solid var(--line-strong)}
.btn.sm{width:auto;padding:9px 14px;font-size:13px}
.error{background:var(--alert-bg);color:var(--alert);padding:10px 12px;border-radius:var(--r-sm);font-size:13.5px}

/* ============ stepper ============ */
.stepper{display:flex;align-items:center;justify-content:space-between;margin:6px 2px 18px;padding:0 6px}
.stepper .st{display:flex;flex-direction:column;align-items:center;gap:5px;flex:0 0 auto;z-index:1}
.stepper .st .n{width:28px;height:28px;border-radius:50%;display:grid;place-items:center;
  font-size:13px;font-weight:800;background:#fff;border:2px solid var(--line-strong);color:var(--faint)}
.stepper .st.done .n,.stepper .st.active .n{background:var(--brand);border-color:var(--brand);color:#fff}
.stepper .st .t{font-size:11px;color:var(--muted)}
.stepper .st.active .t{color:var(--brand);font-weight:700}
.stepper .line{flex:1;height:2px;background:var(--line-strong);margin:0 -4px;margin-bottom:16px}
.stepper .line.done{background:var(--brand)}

/* wizard steps */
.wstep{display:none} .wstep.active{display:block}

/* camera */
.cam-wrap{position:relative;background:#161310;border-radius:var(--r);overflow:hidden;aspect-ratio:3/4;
  display:grid;place-items:center}
.cam-wrap video,.cam-wrap img{width:100%;height:100%;object-fit:cover}
.cam-shot{position:absolute;bottom:16px;left:50%;transform:translateX(-50%);width:64px;height:64px;
  border-radius:50%;background:#fff;border:4px solid rgba(255,255,255,.4)}
.cam-hint{text-align:center;color:var(--muted);font-size:12.5px;margin-top:10px}
.captured{text-align:center}
.captured .ok{width:56px;height:56px;border-radius:50%;background:var(--ok-bg);color:var(--ok);
  display:grid;place-items:center;margin:4px auto 8px;font-size:26px}
img.evidence{max-width:100%;border-radius:var(--r-sm);border:1px solid var(--line)}

/* review summary */
.sum-row{display:flex;justify-content:space-between;gap:12px;padding:9px 0;border-bottom:1px solid var(--line)}
.sum-row:last-child{border:0}
.sum-row .k{color:var(--muted);font-size:13px}
.sum-row .v{font-weight:600;text-align:right}

/* success */
.success{text-align:center;padding:26px 8px}
.success .big{width:76px;height:76px;border-radius:50%;background:var(--ok-bg);color:var(--ok);
  display:grid;place-items:center;font-size:38px;margin:0 auto 14px}
.success .rid{display:inline-block;margin:10px 0;font-weight:800;letter-spacing:1px;
  background:var(--brand-soft);color:var(--brand);padding:8px 16px;border-radius:var(--r-sm)}

/* report list card */
.rcard{display:block;color:inherit}
.rcard .top{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}
.rcard .code{font-weight:800;font-size:13.5px}
.rcard .cat{font-weight:700;margin-top:2px}
.rcard .loc{color:var(--muted);font-size:12.5px;margin:2px 0}
.rcard .desc{color:var(--muted);font-size:13px;margin:4px 0 8px;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.rcard .foot{display:flex;justify-content:space-between;align-items:center}

/* tabs */
.tabs{display:flex;gap:6px;overflow-x:auto;margin:2px 0 12px;-webkit-overflow-scrolling:touch}
.tabs button{border:1px solid var(--line-strong);background:#fff;color:var(--muted);
  border-radius:999px;padding:7px 14px;font-size:13px;font-weight:600;white-space:nowrap}
.tabs button.on{background:var(--brand);border-color:var(--brand);color:#fff}

/* timeline */
.timeline{list-style:none;padding:0;margin:8px 0}
.timeline li{position:relative;padding:0 0 14px 20px;border-left:2px solid var(--line-strong)}
.timeline li:before{content:"";position:absolute;left:-6px;top:2px;width:10px;height:10px;border-radius:50%;
  background:#fff;border:2px solid var(--line-strong)}
.timeline li.done:before{background:var(--brand);border-color:var(--brand)}
.timeline li:last-child{border-color:transparent}

/* ============ bottom nav ============ */
.bottomnav{position:fixed;left:0;right:0;bottom:0;z-index:30;display:flex;background:#fff;
  border-top:1px solid var(--line);height:var(--nav-h);padding-bottom:env(safe-area-inset-bottom)}
.bottomnav a{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;
  color:var(--faint);font-size:10.5px;font-weight:600;text-decoration:none}
.bottomnav a svg{width:21px;height:21px}
.bottomnav a.on{color:var(--brand)}

/* login */
.auth-wrap{min-height:100dvh;display:flex;flex-direction:column}
.auth-hero{position:relative;height:200px;background:var(--brand-soft);overflow:hidden}
.auth-hero img{width:100%;height:100%;object-fit:cover}
.auth-hero .brandmark{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;
  justify-content:center;gap:8px;background:linear-gradient(180deg,rgba(255,255,255,.1),rgba(255,255,255,.75))}
.auth-hero .brandmark img{width:56px;height:56px;object-fit:contain}
.auth-hero .brandmark b{color:var(--brand);font-size:15px;letter-spacing:.5px}
.auth-card{background:#fff;margin:-28px 16px 0;border-radius:var(--r-lg);border:1px solid var(--line);
  box-shadow:var(--shadow);padding:22px 18px;position:relative}
.auth-card h1{text-align:center;font-size:20px;margin:0}
.auth-card .sub{text-align:center;color:var(--muted);font-size:12.5px;margin:2px 0 16px}
.seg{display:flex;background:var(--brand-soft);border-radius:var(--r-sm);padding:3px;margin-bottom:14px}
.seg button{flex:1;border:0;background:transparent;color:var(--muted);font-weight:700;font-size:13px;
  padding:9px;border-radius:8px}
.seg button.on{background:#fff;color:var(--brand);box-shadow:var(--shadow)}
.auth-foot{text-align:center;color:var(--faint);font-size:12px;margin:14px 0 24px}

@media(min-width:560px){ .app-main,.auth-card{max-width:460px;margin-left:auto;margin-right:auto} }
:focus-visible{outline:3px solid var(--brand);outline-offset:2px}
[hidden]{display:none!important}
```

- [ ] **Step 2:** `python -c "print(open('static/css/app.css').read().count('--brand'))"` → non-zero (sanity).

---

### Task 2: SVG brand placeholders

**Files:** create `static/img/glb-logo.svg`, `static/img/campus-hero.svg`

- [ ] **Step 1:** `static/img/glb-logo.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="GL Bajaj">
<circle cx="32" cy="32" r="30" fill="#7a3b2e"/>
<circle cx="32" cy="32" r="25" fill="none" stroke="#e7c9a8" stroke-width="1.5"/>
<text x="32" y="38" text-anchor="middle" font-family="Georgia,serif" font-size="18" font-weight="700" fill="#fff">GLB</text>
</svg>
```

- [ ] **Step 2:** `static/img/campus-hero.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 360" role="img" aria-label="GL Bajaj campus">
<defs><linearGradient id="s" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#f0e4da"/><stop offset="1" stop-color="#e2d2c4"/></linearGradient></defs>
<rect width="800" height="360" fill="url(#s)"/>
<g fill="#7a3b2e" opacity="0.9">
<rect x="120" y="150" width="180" height="150"/><rect x="330" y="110" width="140" height="190"/>
<rect x="500" y="160" width="180" height="140"/>
</g>
<g fill="#fff" opacity="0.5">
<rect x="140" y="170" width="20" height="24"/><rect x="180" y="170" width="20" height="24"/>
<rect x="220" y="170" width="20" height="24"/><rect x="350" y="130" width="18" height="22"/>
<rect x="390" y="130" width="18" height="22"/><rect x="430" y="130" width="18" height="22"/>
<rect x="520" y="180" width="20" height="24"/><rect x="560" y="180" width="20" height="24"/>
<rect x="600" y="180" width="20" height="24"/></g>
<rect x="0" y="300" width="800" height="60" fill="#6f8f5f" opacity="0.55"/>
<text x="400" y="336" text-anchor="middle" font-family="Georgia,serif" font-size="20" fill="#4a3a30">GL Bajaj Institute of Technology &amp; Management</text>
</svg>
```

---

### Task 3: `noticed_at` + `affects_academics` columns

**Files:** modify `db/schema.py`, `db/grievances.py`
**Test:** extend `tests/test_grievances_db.py`

- [ ] **Step 1:** `db/schema.py` — in the `grievances` CREATE TABLE, after `spam_flag BOOLEAN DEFAULT FALSE,`:

```sql
    noticed_at         DOUBLE PRECISION,
    affects_academics  BOOLEAN DEFAULT FALSE,
```

- [ ] **Step 2:** `db/grievances.py`:
  - `_COLS`: add `"noticed_at", "affects_academics"` right after `"spam_flag"`.
  - `_DEFAULTS`: add `"noticed_at": None, "affects_academics": False,`.

- [ ] **Step 3:** Add to `tests/test_grievances_db.py`:

```python
def test_new_fields_default_and_persist(memstore):
    u = _reporter()
    g = grievances.insert(reporter_id=u["id"], reporter_name="x", title="t",
                          description="a description here now", location_type="hostels",
                          location_label="Hostels")
    assert g["noticed_at"] is None and g["affects_academics"] is False
    g2 = grievances.update(g["id"], noticed_at=123.0, affects_academics=True)
    assert g2["noticed_at"] == 123.0 and g2["affects_academics"] is True
```

- [ ] **Step 4:** `pytest tests/test_grievances_db.py -q` → PASS.

---

### Task 4: pipeline — form severity wins, new fields, priority tweak, 300-char limit

**Files:** modify `services/validation_service.py`, `services/classification_service.py`, `services/grievance_service.py`
**Test:** extend `tests/test_grievance_pipeline.py`, `tests/test_priority.py`

- [ ] **Step 1:** `services/validation_service.py` — `_DESC_MIN, _DESC_MAX = 10, 300`.

- [ ] **Step 2:** `services/classification_service.py` `priority_score` — after the `sub_zone == "Security"` block, before `return`:

```python
    if g.get("affects_academics"):
        score += 10
```

- [ ] **Step 3:** `services/grievance_service.py` `submit()` — replace the classify block's use of severity. After `cls = ...` (both branches), add:

```python
    from domain.constants import SEVERITIES
    form_sev = sub.get("severity")
    severity = form_sev if form_sev in SEVERITIES else cls["severity"]
```

Then use `severity` (not `cls["severity"]`) in `g_seed` and the `grievances.insert(... severity=severity ...)` call, and include the new fields:

```python
    g_seed = {
        "severity": severity, "category": cls["category"], "status": "reported",
        "created_at": time.time(), "location_type": sub["location_type"],
        "sub_zone": sub.get("sub_zone"),
        "affects_academics": bool(sub.get("affects_academics")),
    }
    priority = classification_service.priority_score(g_seed)
    ...
    g = grievances.insert(
        ...
        category=cls["category"], severity=severity,
        priority_score=priority,
        ...
        noticed_at=sub.get("noticed_at"),
        affects_academics=bool(sub.get("affects_academics")),
        ai_summary=cls["ai_summary"], ai_confidence=cls["confidence"],
        spam_flag=cls["spam_flag"],
    )
```

The high-priority alert check keeps using `cls["severity"] == "high"` — change to `severity == "high"`.

- [ ] **Step 4:** Add to `tests/test_grievance_pipeline.py`:

```python
def test_form_severity_overrides_ai(memstore):
    u = users.create("fs", "FS", "reporter", hash_pin("1"))
    out = gs.submit(_sub(u["id"], description="minor cosmetic paint chip on the wall",
                         severity="high"))
    assert grievances.get_by_code(out["code"])["severity"] == "high"


def test_affects_academics_bumps_priority_and_persists(memstore):
    u = users.create("fa", "FA", "reporter", hash_pin("1"))
    a = gs.submit(_sub(u["id"], severity="low"))
    b_u = users.create("fb", "FB", "reporter", hash_pin("1"))
    b = gs.submit(_sub(b_u["id"], severity="low", affects_academics=True,
                       location_label="Academics Block > Block C > 1st Floor > Room 9"))
    ga = grievances.get_by_code(a["code"]); gb = grievances.get_by_code(b["code"])
    assert gb["affects_academics"] is True
    assert gb["priority_score"] == ga["priority_score"] + 10
```

- [ ] **Step 5:** Add to `tests/test_priority.py`:

```python
def test_affects_academics_adds_ten():
    g = _g(severity="low", category="IT / Network", location_type="playground",
           affects_academics=True)
    assert priority_score(g) == 23   # 10 + 3 + 0 + 10
```

- [ ] **Step 6:** `pytest tests/test_grievance_pipeline.py tests/test_priority.py tests/test_validation.py -q` → PASS.

---

### Task 5: routes — profile, remember-me, bell dot, home campus-health

**Files:** modify `blueprints/faculty/__init__.py`, `blueprints/auth/__init__.py`, `app.py`
**Test:** `tests/test_faculty_ui.py`

**Interfaces:**
- `GET /profile` → `faculty/profile.html` (`user` = full record).
- `POST /profile/pin` (form `current`, `new`) → verify + `users.set_pin` + `audit.add`; redirect `/profile?ok=1` or `?err=...`.
- `home()` also passes `campus_health` = list of 3 dicts `{name, pct}` from `intelligence_service.pulse()` (keys `electrical`, `water`, `cleanliness`).
- `app.py` context processor adds `bell_dot: bool`.
- `auth` login: `remember` form field → 30-day refresh cookie.

- [ ] **Step 1:** `blueprints/faculty/__init__.py` — add imports `from services.auth_service import hash_pin, verify_pin` and `from db import audit`; add routes:

```python
@bp.get("/profile")
def profile_page():
    u = users.get_by_username(g.current_user["username"])
    return render_template("faculty/profile.html", u=u,
                           ok=request.args.get("ok"), err=request.args.get("err"))


@bp.post("/profile/pin")
def profile_pin():
    u = users.get_by_username(g.current_user["username"])
    cur = (request.form.get("current") or "").strip()
    new = (request.form.get("new") or "").strip()
    if not verify_pin(cur, u["pin_hash"]):
        return redirect("/profile?err=Current+PIN+is+incorrect")
    if not (new.isdigit() and 4 <= len(new) <= 8):
        return redirect("/profile?err=New+PIN+must+be+4-8+digits")
    users.set_pin(u["id"], hash_pin(new))
    audit.add(u["username"], "user.self_pin", target_type="user", target_id=u["id"])
    return redirect("/profile?ok=1")
```

- [ ] **Step 2:** `blueprints/faculty/__init__.py` `home()` — add campus health:

```python
@bp.get("/")
def home():
    uid = _uid()
    mine = grievances.list_for_reporter(uid)
    open_count = sum(1 for r in mine if r["status"] not in ("closed", "admin_verified"))
    latest = notices.list_published()[:1]
    from services import intelligence_service
    pk = {d["key"]: d for d in intelligence_service.pulse()}
    health = [{"name": "Electrical", "pct": pk["electrical"]["score"]},
              {"name": "Water", "pct": pk["water"]["score"]},
              {"name": "Cleanliness", "pct": pk["cleanliness"]["score"]}]
    return render_template("faculty/home.html", open_count=open_count,
                           recent=mine[:3], latest_notice=(latest[0] if latest else None),
                           campus_health=health, notice_count=len(notices.list_published()))
```

- [ ] **Step 3:** `app.py` — extend the context processor:

```python
    @app.context_processor
    def _inject():
        from domain.rbac import has_permission
        user = g.get("current_user")
        bell_dot = False
        if user and user["role"] == "reporter":
            try:
                import time as _t
                from db import grievances, users
                u = users.get_by_username(user["username"])
                if u:
                    cut = _t.time() - 72 * 3600
                    bell_dot = any((r["updated_at"] or 0) >= cut and r["status"] != "reported"
                                   for r in grievances.list_for_reporter(u["id"]))
            except Exception:
                bell_dot = False
        return {
            "current_user": user, "GLB": GLB, "bell_dot": bell_dot,
            "can": (lambda perm: bool(user) and has_permission(user["role"], perm)),
        }
```

- [ ] **Step 4:** `blueprints/auth/__init__.py` — in `login()` POST, after `result = auth_service.login(...)` success:

```python
    remember = bool(request.form.get("remember"))
    if remember:
        result.refresh_token = auth_service.create_refresh_token(result.user["username"], days=30)
    target = "/admin" if result.user["role"] == "admin" else "/"
    resp = make_response(redirect(target))
    _set_cookies(resp, result.access_token, result.refresh_token, remember=remember)
    return resp
```

and update `create_refresh_token` in `services/auth_service.py` to accept `days`:

```python
def create_refresh_token(user_id: str, days: int = 7) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": user_id, "iat": now, "exp": now + days * 24 * 3600, "type": "refresh"},
        Config.JWT_SECRET, algorithm=_ALG,
    )
```

and `_set_cookies` in `blueprints/auth/__init__.py`:

```python
def _set_cookies(resp, access: str, refresh: str, remember: bool = False):
    resp.set_cookie(_ACCESS, access, max_age=15 * 60, httponly=True,
                    samesite="Strict", secure=_SECURE, path="/")
    resp.set_cookie(_REFRESH, refresh, max_age=(30 if remember else 7) * 24 * 3600,
                    httponly=True, samesite="Strict", secure=_SECURE, path="/auth/refresh")
    return resp
```

- [ ] **Step 5:** Write `tests/test_faculty_ui.py`:

```python
def _login(c, u="prof.rao", p="1234", **extra):
    return c.post("/login", data={"username": u, "pin": p, **extra})


def test_profile_page_and_pin_change(client):
    _login(client)
    assert client.get("/profile").status_code == 200
    r = client.post("/profile/pin", data={"current": "1234", "new": "5678"})
    assert r.status_code == 302 and "ok=1" in r.headers["Location"]
    # old pin no longer works
    c2 = client.application.test_client()
    assert c2.post("/login", data={"username": "prof.rao", "pin": "1234"}).status_code == 401
    assert c2.post("/login", data={"username": "prof.rao", "pin": "5678"}).status_code == 302


def test_pin_change_rejects_bad_current(client):
    _login(client)
    r = client.post("/profile/pin", data={"current": "0000", "new": "5678"})
    assert "err=" in r.headers["Location"]


def test_home_shows_campus_health(client):
    _login(client)
    r = client.get("/")
    assert b"Campus Health" in r.data or b"campus health" in r.data.lower()


def test_remember_me_sets_long_cookie(client):
    r = _login(client, remember="1")
    setc = r.headers.getlist("Set-Cookie")
    ref = [c for c in setc if c.startswith("up_refresh=")][0]
    assert "Max-Age=2592000" in ref  # 30 days


def test_bottom_nav_has_profile(client):
    _login(client)
    r = client.get("/")
    assert b'href="/profile"' in r.data
```

- [ ] **Step 6:** `pytest tests/test_faculty_ui.py -q` → PASS.

---

## Phase E2 — base template, login, home, profile

### Task 6: `templates/base_faculty.html`

- [ ] Replace with a shell that has: `<header class="app-header">` (logo img, `.h-title` "UniPulse" + `<small>{{ GLB.short }}</small>`, a bell `.icon-btn` linking `/notices` with `{% if bell_dot %}<span class="dot">{% endif %}`, and an `.avatar` linking `/profile` showing the user's initials); `<main class="app-main">{% block content %}`; the 5-item `.bottomnav` (Home, Report, My Reports, Notices, Profile) each an `<a>` with an inline SVG icon + label and `class="on"` when `request.path` matches; keep the manifest/apple-touch/theme-color `<head>` tags, the SW registration script, and the `#pwa-install` button + `beforeinstallprompt` handler exactly as they are now. The bottom nav renders for any logged-in user (not only role reporter — admins viewing a faculty grievance still get it; harmless). Login page hides the nav (it extends a bare variant — see Task 7).

### Task 7: `templates/faculty/login.html`

- [ ] Standalone page (does NOT extend base_faculty — no nav/header). Structure:
  `.auth-wrap` → `.auth-hero` (`<img src="campus-hero.svg">` + `.brandmark` overlay with `glb-logo.svg` + "GL BAJAJ") → `.auth-card` with `<h1>Welcome to UniPulse</h1>`, `.sub` "Campus Grievance Portal", the `.seg` Faculty/Admin toggle (JS swaps a hidden helper text + nothing else — both post to `/login`), form (`username` placeholder "Username / Email", `pin` type=password, `<label class="check"><input type="checkbox" name="remember">Remember me</label>`, `<button class="btn">Login</button>`), `{% if error %}<p class="error">`, `.auth-foot` "Keeping our campus better, together". Keep `<link rel="stylesheet" ...app.css>` + `<title>`.

### Task 8: `templates/faculty/home.html`

- [ ] Extends base_faculty. Content: `<h2>Hello, {{ current_user.display_name }} 👋</h2>` + `<p class="muted">{{ current_user.department or 'Faculty' }}</p>`; `<a class="action-card" href="/report"><span><b>Report an Issue</b><span>Spot · Share · Resolve</span></span><span class="arrow">→</span></a>`; `.stat-grid` with two `.stat` cards linking `/my-reports` ("{{ open_count }} Open", label "My Reports") and `/notices` ("{{ notice_count }}", "Campus Notices"); `<h3>Campus Health</h3>` + `.health-row` of 3 `.health` (`.pct` = `{{ h.pct }}%`, `.lbl` = `{{ h.name }}`, `.bar>i` width `{{ h.pct }}%`); `{% if latest_notice %}` a `.card` "CAMPUS NOTICE" + title + body + link `/notices`; `{% if recent %}<h3>Recent</h3>` list of `.rcard` (see my_reports card markup).

### Task 9: `templates/faculty/profile.html`

- [ ] Extends base_faculty. `.screen-title` "Profile". A `.card` showing `.avatar` (large) + display_name + `@username` + department + contact (or "—"). `{% if ok %}<p class="error" style="background:var(--ok-bg);color:var(--ok)">PIN updated.</p>` / `{% if err %}<p class="error">{{ err }}</p>`. `<h3>Change PIN</h3>` form → `/profile/pin` (fields `current`, `new`, both type=password inputmode=numeric; `<button class="btn">Update PIN</button>`). A `<a class="btn ghost" href="/logout">Log out</a>`.

- [ ] **After Tasks 6-9:** `pytest tests/test_faculty_routes.py tests/test_faculty_ui.py tests/test_routes_smoke.py -q` → PASS (fix any assertion that keyed on old markup — keep the strings the tests check: "Report an Issue" on home + report, "UniPulse" on login).

---

## Phase E3 — report wizard + camera

### Task 10: `templates/faculty/report.html` + `static/js/report.js`

- [ ] **report.html** extends base_faculty. `.screen-title` with a back-arrow (JS: go to previous wstep or `/`). The `.stepper` (3 steps: Photo / Details / Submit — classes `done`/`active` toggled by JS, `.line` between). Then `#wiz` (keep `data-picker` + `data-typenames`) containing:
  - `.wstep active data-step="photo"`: `.cam-wrap` with `<video id="cam" playsinline hidden>` + `<img id="shot" hidden>` + `<button id="snap" class="cam-shot" hidden>`; a row of `.btn.ghost` "Gallery" (`#pick`, triggers a hidden `<input type=file id="photo" accept="image/*" capture="environment" aria-label="Photo of the problem" hidden>`) and `.btn` "Camera" (`#startcam`); `.cam-hint` "A clear image helps in faster resolution." When a shot/file is ready: swap to the `.captured` view — `.ok` check, "Photo captured!", `#preview` img, `.btn` "Proceed to Fill Form" (`#to-details`), `.btn.ghost` "Retake" (`#retake`).
  - `.wstep data-step="loc"`: **"Report an Issue"** heading kept. Block ▾ (`#f-block`), Floor ▾ (`#f-floor`), Room (`#f-room` text w/ a pin affordance), Outer-Area sub-zone ▾ (`#f-sub`, shown only for that type — but note: type is chosen how? Add a compact type `.pill-row` at the top of this step, ids unchanged from the old `type-pills` pattern), then `<label>Priority</label><div class="pri-pills">` 3 `<button type=button aria-pressed>` Low/Medium/High (`#pri`), `.btn` "Next →" (`#to-desc`).
  - `.wstep data-step="desc"`: `<textarea id="desc" maxlength="300">`, `.counter` `<span id="cc">0</span>/300`; `<label>When did you notice?</label><input type="datetime-local" id="noticed">`; `<label class="check"><input type="checkbox" id="affects"> This is affecting classes / academic work</label>`; `.btn` "Review →" (`#to-review`).
  - `.wstep data-step="review"`: **"Review & Submit"**. `#preview2` img, `.sum-row`s (Location, Priority, Description, When). `.card` note "Your report will be routed to the concerned team automatically." `.btn` "Submit Report" (`#submit`).
  - `.wstep data-step="done"`: `.success` — `.big` ✓, `<h2>Report Submitted!</h2>`, `<p class="muted">Your report has been successfully reported.</p>`, `.rid` `#done-code`, priority chip, `#done-recurring` note, `<a class="btn" href="/my-reports">View in My Reports</a>` + `<a class="btn ghost" href="/report">Report Another Issue</a>`.
  Keep `{% block scripts %}<script src="report.js">`.

- [ ] **report.js** — rebuild. State: `{photo_b64, photo_mime, type, block_no, floor, room, sub_zone, description, severity, noticed_at, affects_academics, ai}`. Functions:
  - `showStep(name)` + stepper class update (photo→1, loc/desc→2, review/done→3).
  - **Camera:** `#startcam` → `navigator.mediaDevices.getUserMedia({video:{facingMode:'environment'}})` → `#cam` visible, `#snap` visible; `#snap` → draw `#cam` to a canvas, `toDataURL('image/jpeg',0.85)`, set state + `#preview`/`#preview2`, stop tracks, show `.captured`. On `getUserMedia` reject/throw → hide camera UI, click `#photo` (file input). `#pick` → click `#photo`. `#photo` change → FileReader → same captured flow. `#retake` → clear state, show camera step start.
  - Location step: type pills build from `picker.types`; drill selects from `picker.academics_blocks/floors` + room input; sub-zone select for outer_area. Priority pills: click → `aria-pressed` toggle + `state.severity = 'low'|'medium'|'high'`.
  - `#to-details` guard: photo required. `#to-desc` guard: type + (academics→block) + (outer_area→sub) + severity. `#to-review`: desc ≥ 10; capture `noticed` (`new Date(value).getTime()/1000` or null), `affects`.
  - `#to-review` also calls `/report/analyze` (POST `{description, photo_b64, photo_mime}`) to populate `state.ai` and show the AI summary line in the review card (best-effort).
  - `#submit` → POST `/report` with `{description, location_type, block_no, floor, room, sub_zone, photo_b64, photo_mime, severity, noticed_at, affects_academics, ai}` → on 200 fill `.done` view (`#done-code` = out.code, recurring note) and `showStep('done')`; on 400 `alert(errors.join('\n'))`.
  - Back-arrow: `review→desc→loc→photo→/`.

- [ ] **blueprints/faculty `report_submit`** — thread the new fields into `sub`:

```python
    sub = {
        "reporter_id": _uid(),
        "description": (d.get("description") or "").strip(),
        "location_type": d.get("location_type"),
        "block_no": d.get("block_no"), "floor": d.get("floor"),
        "room": d.get("room"), "sub_zone": d.get("sub_zone"),
        "location_label": label,
        "photo_b64": d.get("photo_b64"), "photo_mime": d.get("photo_mime", "image/jpeg"),
        "severity": d.get("severity"),
        "noticed_at": d.get("noticed_at"),
        "affects_academics": bool(d.get("affects_academics")),
        "ai": d.get("ai"),
    }
```

- [ ] **Tests:** add to `tests/test_faculty_ui.py`:

```python
def test_submit_with_form_priority_and_fields(client):
    _login(client)
    r = client.post("/report", json={
        "description": "The tube light in this room is flickering badly since two days",
        "location_type": "academics_block", "block_no": "Block B", "floor": "2nd Floor",
        "room": "204", "photo_b64": "aGVsbG8=", "photo_mime": "image/jpeg",
        "severity": "high", "affects_academics": True, "noticed_at": 1724990000.0})
    assert r.status_code == 200
    code = r.get_json()["code"]
    from db import grievances
    g = grievances.get_by_code(code)
    assert g["severity"] == "high"
    assert g["affects_academics"] is True
    assert g["noticed_at"] == 1724990000.0


def test_report_page_has_stepper_and_camera(client):
    _login(client)
    html = client.get("/report").data
    assert b"stepper" in html and b'id="startcam"' in html
    assert b"Report an Issue" in html
```

- [ ] `pytest tests/test_faculty_ui.py tests/test_faculty_routes.py -q` → PASS.

---

## Phase E4 — my-reports, detail, notices, admin field surfacing, polish

### Task 11: `templates/faculty/my_reports.html` + `grievance_detail.html` + `notices.html`

- [ ] **my_reports.html** — `.screen-title` "My Reports"; `.tabs` All/Open/In Progress/Resolved (JS filters the loaded list client-side by a `status`→bucket map: open={reported,verified}, in_progress={assigned,in_progress}, resolved={resolved,admin_verified,closed}); the JS `fetch('/my-reports/data')` renders `.rcard` list items:

```html
<a class="card rcard" href="/grievance/${g.code}">
  <div class="top"><div><div class="code">${g.code}</div>
    <div class="cat">${g.category || 'Pending review'}</div></div>
    <span class="badge-pri ${sev}">${sevLabel}</span></div>
  <div class="loc">${g.location_label}</div>
  <div class="desc">${g.title || ''}</div>
  <div class="foot"><span class="chip ${g.status}">${g.status.replace('_',' ')}</span>
    <span class="tiny muted">${date}</span></div>
</a>
```
  `/my-reports/data` must also return `title` and `severity` — add those two keys to the dict in `my_reports_data()`.

- [ ] **grievance_detail.html** — restyle to cards: `.screen-title` back-arrow + `{{ g.code }}` + status chip; photo; a `.card` "Reported" with description + AI summary + (noticed_at as a readable date if set) + "Affecting academics" line if true; recurring `.card` if `group`; assignment `.card` if `responsible_unit`; `<h3>Progress</h3>` the `steps` as a `.timeline` (done/current); `<h3>Activity</h3>` the `timeline` events; resolution evidence cards. Keep the `steps`/`timeline`/`evidence`/`group` context from the existing route.

- [ ] **notices.html** — `.screen-title` "Campus Notices"; each notice a `.card` with title (bold) + body + a tiny muted date.

### Task 12: admin detail surfacing + `/my-reports/data` keys + full green

- [ ] **`blueprints/faculty` `my_reports_data`** — add `"title": r["title"], "severity": r["severity"]` to each row dict.

- [ ] **`templates/admin/detail.html`** — in the "Description" card, after the AI line, add:

```html
  {% if g.noticed_at %}<p class="muted tiny">Noticed: {{ g.noticed_at | int }}</p>{% endif %}
  {% if g.affects_academics %}<p class="muted tiny">⚠ Reporter marked this as affecting classes / academic work</p>{% endif %}
```

- [ ] **Clean + full suite:**

```bash
cd "C:/Users/rocky/OneDrive/Desktop/unipulse/unipulse-campus"
rm -rf __pycache__ */__pycache__ */*/__pycache__ .pytest_cache tests/__pycache__ scripts/__pycache__
python -m pytest -q
python -m compileall -q app.py wsgi.py config.py db domain services blueprints ai scripts
```
Expected: all pass (135 + ~13 new), compile OK.

- [ ] **Manual render check:**

```bash
python -c "
from app import create_app
from scripts import seed_demo
app = create_app(); seed_demo.build()
c = app.test_client(); c.post('/login', data={'username':'prof.rao','pin':'1234'})
for p in ['/','/report','/my-reports','/notices','/profile']:
    r = c.get(p); print(f'{p:14s} {r.status_code}  css={b\"app.css\" in r.data}  nav={b\"bottomnav\" in r.data}')
lg = app.test_client().get('/login'); print('/login        ', lg.status_code, b'Welcome to UniPulse' in lg.data)
" 2>&1 | grep -v "storage_service\|\[db\]"
```
Expected: every faculty route 200 with the css + nav present; login shows the welcome copy.

- [ ] **Update the memory note** — faculty mobile UI redesign done; admin restyle is the next pass.

---

## Self-Review

**Spec coverage:** restrained palette (Task 1) · category AI-only / priority-picked → severity (Task 4, 10) · in-app camera + fallback (Task 10) · codes unchanged · desc 300 (Task 4) · SVG placeholders (Task 2) · `noticed_at` + `affects_academics` (Tasks 3-5, surfaced Task 12) · campus health on home (Task 5, 8) · profile + change PIN (Task 5, 9) · bell dot (Task 5, 6) · remember-me (Task 5) · all 10 screens (Tasks 6-11). ✅

**Placeholder scan:** backend/logic steps have full code + tests; asset steps (CSS Task 1, SVG Task 2, report.js Task 10) have full content; the plainer templates (Tasks 6-11) are specified by exact structure + the class names from Task 1's CSS + the ids/field-names the JS and tests require — deterministic for the executor who also wrote Task 1/10.

**Type consistency:** `severity` from form is validated against `SEVERITIES` before use (Task 4); `/my-reports/data` gains `title`+`severity` and the JS + `test_submit_with_form_priority_and_fields` rely on the same keys; `create_refresh_token(user_id, days=7)` new signature is called in 2 places (auth login + refresh) — refresh keeps the default; `_set_cookies(resp, a, r, remember=False)` new kwarg is optional so the logout/refresh callers are unaffected. `bell_dot` added to context processor dict alongside the existing keys. ✅
