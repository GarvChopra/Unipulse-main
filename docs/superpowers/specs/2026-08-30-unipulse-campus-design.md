# UniPulse — GL Bajaj Campus Infrastructure Intelligence — Design Spec

Date: 2026-08-30
Status: approved (design sections 1–6 confirmed by product owner)
Supersedes: the Phase-1 "backend fork & strip" scope in `../../../PHASE1_NOTES.md`

## 1. Context & goal

A campus-specific rebuild of AreaPulse for **GL Bajaj Institute of Technology and
Management**. Faculty report campus infrastructure problems from a phone; a single
Super Admin ("Sir") reviews, routes, tracks and verifies every grievance. The
system turns individual reports into a live picture of infrastructure health,
recurring failures and maintenance priorities.

One-line architecture: **Report → Understand → Prioritize → Assign → Resolve →
Verify → Learn**.

Source material: `CLAUDE.md` (authoritative phase intent), `AreaPulse_College_
Campus_MVP_Plan.docx`, `AreaPulse_Campus_Feature_List.docx`. Where the MVP plan and
CLAUDE.md conflict, CLAUDE.md wins — notably **no map / heatmap in this MVP**
(structured location data only, so a map *could* be added later without rework).

Reference code: `../areapulse-2` (github.com/shash-shukla06/Areapulse) — reuse the
engine, not the civic product.

## 2. Scope

### In (Feature List)
Faculty PWA (report flow, My Reports, timeline, notices, installable). Super Admin
web portal (KPI dashboard, grievance queue, detail, assignment to Responsible Unit,
7-step status workflow, verified resolution with before/after evidence, audit
trail) — responsive, doubles as the admin mobile experience. AI layer
(classification, severity, priority, spam soft-filter, duplicate/**recurring**
detection, Infrastructure Pulse, Gap Intelligence). Email notifications (Resend).
RBAC (roles → permissions; generic so a 2nd admin/coordinator is a config change).

### Out
Geographic map / heatmap (P2, deferred). Voice input (P2). WhatsApp bot. Community
feed. AI complaint-letter + email-to-government-authority. Public stats page.
Upvotes / crowd-escalation. Ban/strike system. Firebase backend. Google OAuth.
scikit-learn ML spam model. Student registration. Native app. Multi-campus tenancy
(single campus; `locations.campus` is a text default). Offline photo-queue & Web
Push (PWA is install + shell-offline only).

### Non-goals
Preserving any backwards compatibility with the reference's civic API or schema.
This is a ground-up campus project that reuses selected modules.

## 3. Architecture

Flask app factory + blueprints. Server-rendered Jinja + vanilla JS, no build step.
Postgres primary (via `DATABASE_URL`), in-memory fallback for dev/demo/tests. Groq
for AI with deterministic/keyword fallback so the app runs fully offline.

### Kept from the reference (trimmed)
- Postgres connection-pool + in-memory fallback pattern → `db/`
- JWT access/refresh in httpOnly `SameSite=Strict` cookies + bcrypt PIN hashing → `services/auth_service.py`
- Groq client + vision/text calls → `ai/engine.py` (~1900 → ~400 lines)
- ImageKit → base64-passthrough image upload → `services/storage_service.py`
- Resend email → `services/notification_service.py`
- Submit-pipeline skeleton: validate → classify → dedup → insert

### Target layout
```
unipulse/
  app.py            app factory, blueprint registration, startup (init db, seeds)
  config.py         env config (DATABASE_URL, GROQ_API_KEY, JWT_SECRET, RESEND_API_KEY,
                    IMAGEKIT_*, APP_ENV, SECRET_KEY)
  wsgi.py           gunicorn entrypoint
  db/
    pool.py         connection pool + _state + in-memory store + init_db()
    schema.py       DDL (CREATE TABLE ... IF NOT EXISTS) + _ensure_schema(conn)
    grievances.py   CRUD + list/filter/sort queries + code generator
    evidence.py     add / list by grievance
    timeline.py     append event / list by grievance
    recurring.py    group CRUD, attach grievance, recount
    users.py        account CRUD, auth lookup
    notices.py      CRUD
    locations.py    master data + seed + picker queries
    audit.py        append / list
  domain/
    constants.py    CATEGORIES, RESPONSIBLE_UNITS, GRIEVANCE_STATUSES + transitions,
                    LOCATION_TYPES, OUTER_AREA_SUBZONES, SLA_HOURS, PULSE_DOMAINS,
                    RECURRING_WINDOW_DAYS, GLB (name/short/domain/colors), CODE_PREFIX
    models.py       dataclasses: User, Grievance, Evidence, TimelineEvent,
                    RecurringGroup, Notice, Location, AuthUser
    rbac.py         Permission constants, ROLE_PERMISSIONS map,
                    has_permission(role, perm), require_permission() decorator
  services/
    auth_service.py         hash_pin, verify_pin, JWT create/decode, login(username, pin),
                            refresh, login rate-limit
    grievance_service.py    submit(submission) pipeline; workflow transitions with guards
    classification_service.py  classify(desc, photo) -> {category, severity, ai_summary,
                               confidence, spam_flag}; priority_score(grievance) -> 0..100
    duplicate_service.py    find_recurring(location_label, category, reporter_id, now)
    intelligence_service.py pulse() -> [{domain, score, trend, factors}]; gaps() -> [...]
    storage_service.py      upload_image(bytes, mime) -> (key, url, thumb_url)
    validation_service.py   validate_submission(sub) -> [errors]
    notification_service.py send_status_email(grievance, new_status);
                            send_high_priority_alert(grievance)
  ai/
    engine.py       Groq client; is_available(); classify_text(); classify_image();
                    campus prompts; keyword fallback map for the 6 categories
  blueprints/
    auth/__init__.py       GET/POST /login, GET /logout, POST /auth/refresh
    faculty/__init__.py    GET / ; GET /report ; POST /report/analyze ; POST /report ;
                           GET /my-reports (+ /data) ; GET /grievance/<code> ; GET /notices
    admin/__init__.py      GET /admin ; /admin/grievances (+ /data) ;
                           /admin/grievances/<code> ; POST .../verify|category|assign|
                           status|evidence|verify-resolution|close|note ;
                           /admin/recurring ; /admin/pulse ; /admin/gaps ;
                           /admin/analytics (+ /export.csv) ;
                           GET/POST /admin/notices|users|locations ; GET /admin/audit
  templates/
    base_faculty.html  base_admin.html  login.html
    faculty/*.html     admin/*.html
  static/
    css/  js/  icons/  manifest.json  service-worker.js
  tests/
    conftest.py (in-memory app fixture)  test_grievance_pipeline.py
    test_recurring.py  test_priority.py  test_workflow_gates.py  test_rbac.py
    test_routes_smoke.py
  docs/superpowers/specs/2026-08-30-unipulse-campus-design.md   (this file)
```

## 4. Data model

Postgres primary; the in-memory store mirrors the same shapes as lists of dicts.
Timestamps are epoch floats.

### users
`id · username(unique) · display_name · role('reporter'|'admin') · pin_hash(bcrypt) ·
department · contact · is_active(bool) · created_at · created_by`

### locations
`id · parent_id(nullable FK) · location_type('academics_block'|'hostels'|'mess_canteen'|
'playground'|'outer_area'|'block'|'floor') · name · full_path(unique) · is_active(bool)`
Seed: 5 top-level types, 5 Outer-Area sub-zones, starter Academics blocks
(A–D) and floors (Ground–4). Room is entered as free text at report time.

### grievances
`id · code(unique, e.g. GLB-CAMP-00001) · reporter_id(FK users) · reporter_name ·
title · description · category(nullable; one of the 6) · category_confirmed(bool) ·
severity('low'|'medium'|'high') · priority_score(int 0..100) ·
status(7-step, CHECK) · location_type · block_no · floor · room · sub_zone ·
location_label(text; dedup key component) · responsible_unit · assignee ·
assigned_at · due_at · recurring_group_id(nullable FK) · ai_summary · ai_confidence ·
primary_photo_url · thumbnail_url · created_at · updated_at · resolved_at · closed_at`

`status ∈ {reported, verified, assigned, in_progress, resolved, admin_verified, closed}`

### evidence
`id · grievance_id(FK, cascade) · kind('report'|'resolution_before'|'resolution_after') ·
image_url · image_key · thumbnail_url · note · uploaded_by · uploaded_at`

### timeline_events
`id · grievance_id(FK, cascade) · event_type('created'|'status_change'|'assigned'|
'category_corrected'|'evidence_added'|'note'|'merged_recurring') · from_value ·
to_value · actor · actor_role · note · created_at`

### recurring_groups
`id · location_label · category · title · report_count(int) · reporter_count(int) ·
first_reported_at · last_reported_at · status('active'|'resolved') ·
primary_grievance_id`

### notices
`id · title · body · audience('all') · created_by · created_at · is_published(bool) ·
expires_at(nullable)`

### audit_log
`id · actor · action · target_type · target_id · detail(jsonb) · created_at`
For admin actions not scoped to one grievance (login, user create, notice publish,
location edit). Grievance-scoped actions live in `timeline_events`.

### Derived, not stored
Infrastructure Pulse and Gap Intelligence are computed on demand from `grievances`.

## 5. Domain constants

- **Categories:** Electric, Plumbing, Civil, Mechanical, Power, IT / Network
- **Responsible Units:** College → Infrastructure, Sanitation, Housekeeping,
  Landscaping, Mess, Parking · Academics → Class, Lab
- **Status workflow & allowed transitions:** forward only —
  `reported → verified → assigned → in_progress → resolved → admin_verified → closed`.
  Each step advances by exactly one, driven by a specific admin action
  (verify / assign / status / verify-resolution / close). The only non-forward
  transition in the MVP is an explicit, logged admin **reopen**:
  `resolved | admin_verified → in_progress`.
- **GAP_THRESHOLD = 4** (min grievances in a (location, category) bucket to surface a gap).
- **Location hierarchy:** Academics Block → Block → Floor → Room; Hostels;
  Mess / Canteen; Playground; Outer Area → {Common/Electrical, Security, Lawn Area,
  Sewage, Drainage}
- **SLA_HOURS** (campus defaults, tunable): Electric 24, Power 24, Plumbing 48,
  Mechanical 72, Civil 120, IT/Network 48. `due_at = assigned_at + SLA_HOURS[category]`.
- **PULSE_DOMAINS:** Electrical (Electric+Power), Water/Plumbing (Plumbing),
  Classrooms (category any + location_type academics_block), IT (IT/Network),
  Cleanliness (Civil/housekeeping signals), Security (Outer Area / sub_zone Security).
- **RECURRING_WINDOW_DAYS = 14**
- **CODE_PREFIX = "GLB-CAMP-"**, zero-padded to 5 digits.
- **GLB:** name "GL Bajaj Institute of Technology and Management", short "GL Bajaj",
  product "UniPulse", theme colors.

## 6. RBAC

`domain/rbac.py`: `ROLE_PERMISSIONS = {reporter: {...}, admin: {...}}`.

| Permission | reporter | admin |
|---|:-:|:-:|
| grievance.create, grievance.view_own | ✅ | ✅ |
| grievance.view_all | | ✅ |
| grievance.verify | | ✅ |
| grievance.correct_category | | ✅ |
| grievance.assign | | ✅ |
| grievance.change_status | | ✅ |
| grievance.verify_resolution | | ✅ |
| grievance.close | | ✅ |
| analytics.view | | ✅ |
| notice.manage, user.manage, location.manage, audit.view | | ✅ |

- `@require_permission('x')` on routes → 403 JSON for `/…/data`/POST, redirect to
  `/login` for pages.
- `admin` blueprint `before_request`: require role `admin`.
- `faculty` blueprint `before_request`: require any authenticated user.
- Jinja global `can(perm)` for button visibility.

## 7. Auth

Username + PIN for all users. bcrypt PIN hash. On login → JWT access (15 min) +
refresh (7 d) in httpOnly `SameSite=Strict` cookies. `before_request` middleware
decodes access cookie → `flask.g.current_user` (AuthUser: user_id, username,
display_name, role, department); context processor exposes it + `can()` to
templates. `/auth/refresh` rotates. `/logout` clears cookies. **No `session`, no
OAuth.** Login attempts rate-limited (in-memory counter per username+IP, e.g. 5/5min).
Seeds: `admin`/`0000` + ~4 demo faculty. No self-registration; admin creates
faculty via `/admin/users`.

## 8. Faculty report pipeline

`services/grievance_service.submit(submission)`:
1. `validate_submission` — description ≥ 10 chars, location present & valid, photo present.
2. Same-reporter true-duplicate guard: same reporter + same `location_label` + same
   `category` within 24h → reject ("You already reported this").
3. `classification_service.classify` — reuse the result the wizard already fetched
   from `/report/analyze` if supplied and unchanged; else call now. Yields category,
   severity, ai_summary, confidence, spam_flag.
4. `duplicate_service.find_recurring(location_label, category, reporter_id, now)` —
   other non-closed grievances, same location_label + category, within
   RECURRING_WINDOW_DAYS. If found: ensure a `recurring_group` (create from the
   pair if none), set `recurring_group_id` on this grievance, bump
   `report_count`/`reporter_count`/`last_reported_at`, add `merged_recurring`
   timeline events.
5. Insert `grievances` (code from generator, status `reported`, `priority_score`
   from the deterministic formula), `evidence(kind='report')`, `timeline_events('created')`.
6. spam_flag is stored/surfaced but never blocks.
Returns `{code, recurring: {group_id, report_count} | None}`.

## 9. Priority score (deterministic)

`priority_score(g) = clamp(0..100,  base_severity + category_risk + recurrence + age + area)`
- base_severity: high 45, medium 25, low 10
- category_risk: Electric/Power/Civil +15, Mechanical +8, Plumbing +6, IT/Network +3
- recurrence: in an active group +2 per extra report, capped +20
- age: +1 per day since `created_at` in `reported`/`verified`, capped +15
- area: location_type academics_block +8, mess_canteen +6, outer_area sub_zone
  Security +8, hostels +4
Recomputed on status change, recurrence change, and a nightly-ish pass (on admin
queue load if `updated_at` stale). Explainable — the factors are shown in the detail view.

## 10. Infrastructure Pulse & Gap Intelligence

`pulse()` → for each PULSE_DOMAIN: `score 0..100` from open-count, severity mix,
active-recurrence count, mean age of open, and 30-day resolution rate; `trend`
(vs previous 30 days); `factors` (the 2–3 largest contributors, as text). Presented
as an operational indicator, explicitly not a scientific measurement.

`gaps()` → group non-closed grievances by (location bucket, category); for each
group with `count ≥ GAP_THRESHOLD (default 4)` emit
`{location, category, count, recurring_count, recommended_action}` where
`recommended_action` comes from a template map keyed by category. Ranked by
`count + 2*recurring_count`.

## 11. Testing

pytest against the in-memory backend (no Postgres). Fixtures build a fresh app +
store per test.
- `test_grievance_pipeline` — validate → classify(stub) → insert; code format; evidence + timeline written.
- `test_recurring` — 2nd matching report forms a group; counts; window boundary; different category/location does not match; 24h same-reporter reject.
- `test_priority` — formula boundaries and clamp.
- `test_workflow_gates` — illegal transitions rejected; `resolved` blocked without `resolution_after` evidence + note; each transition writes a timeline event.
- `test_rbac` — reporter blocked from admin routes/permissions; admin allowed; `can()`.
- `test_routes_smoke` — login (both roles), faculty report happy path, admin queue/detail/actions, 404s for removed routes.
Groq and Resend are stubbed in tests; `ai/engine.is_available()` returns False so
the keyword/deterministic fallbacks run.

## 12. Build phases (each = review checkpoint)

- **Phase 0 — Restructure & strip.** Reorganise `unipulse-campus/` into §3 layout;
  delete out-of-scope features and their deps (scikit-learn, numpy, imagehash,
  firebase-admin, twilio); trim `ai_engine.py` → `ai/engine.py`; app factory +
  blueprint registration; skeleton boots with auth only.
- **Phase A — Data foundations.** `constants.py`; new schema + `db/` modules +
  `models.py`; `GLB-CAMP-#####` generator; `rbac.py` + decorator + `can()`; seeds
  (admin, demo faculty, locations, demo notices).
- **Phase B — Faculty PWA.** `auth` + `faculty` blueprints; `grievance_service`
  submit pipeline; `classification_service` + `ai/engine.py` prompts + keyword
  fallback; `duplicate_service`; `storage_service`; `base_faculty.html` + templates
  + JS; `manifest.json` + `service-worker.js` + icons.
- **Phase C — Super Admin portal.** `admin` blueprint + responsive `base_admin.html`;
  dashboard, queue, detail, all workflow actions (gated + audited), verified-
  resolution gate, recurring screen, notices/users/locations CRUD, audit log.
- **Phase D — Intelligence layer.** `priority_score` + recompute hooks;
  `intelligence_service.pulse()` + `.gaps()`; Pulse strip + `/admin/pulse` +
  `/admin/gaps`; priority-ranked queue default; spam soft-flag surfaced.
- **Phase E — Platform polish.** Resend email (status → reporter, high-priority →
  admin); `/admin/analytics` + CSV export; PWA polish + a11y; demo-data script
  incl. the MVP §18 "Room 204 projector" recurring scenario.

## 13. Open questions / deferred

- Real GL Bajaj block/floor/room inventory — seeding a starter set; admin edits via `/admin/locations`.
- Forced first-login PIN change — deferred.
- Web Push / offline submit queue — deferred.
- Pulse/Gap result caching (materialized view) — only if perf needs it.
- `Campus` entity / multi-tenant — single campus for MVP.
