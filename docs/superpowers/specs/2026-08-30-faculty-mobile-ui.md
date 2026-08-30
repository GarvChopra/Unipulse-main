# UniPulse — Faculty Mobile UI Redesign — Design Spec

Date: 2026-08-30
Status: approved (mockup `../../../../ui-mockups.png` + Q&A)
Scope: the faculty PWA only (10 screens). Admin portal restyle is a later pass.

## Decisions

- **Palette is restrained** — white page backgrounds everywhere, one brown accent
  (`#7a3b2e`), warm neutrals, and at most 3 status colors used only inside
  chips/badges. Do NOT reproduce the mockup's cream/gold washes.
- **Category stays AI-only** — no category control on the report form. Faculty
  choose location (block/floor/room), a **Priority** (Low/Medium/High → stored as
  the grievance `severity`), and write the description. AI still sets `category`
  and `ai_summary`; the admin confirms/corrects.
- **Real in-app camera** (`getUserMedia`) with a styled `<input type=file capture>`
  fallback when the camera API is unavailable or denied.
- **Grievance codes stay `GLB-CAMP-#####`** (unchanged).
- Description limit → **300 chars** with a live `n/300` counter.
- Brand assets (GL Bajaj crest, campus hero photo) are supplied by the user later;
  ship SVG placeholders at `static/img/glb-logo.svg` and `static/img/campus-hero.svg`
  and reference those paths so a drop-in replacement is trivial.

## Backend deltas

- `grievances` gains two nullable columns: `noticed_at` (DOUBLE PRECISION),
  `affects_academics` (BOOLEAN DEFAULT FALSE). Add to `schema.py` DDL,
  `db/grievances.py` `_COLS` + `_DEFAULTS`.
- `grievance_service.submit(sub)` — if `sub["severity"]` is a valid `SEVERITIES`
  value, it wins over the AI/keyword severity; `category`/`ai_summary` still come
  from `classification_service.classify`. Passes `noticed_at` + `affects_academics`
  through to `grievances.insert`.
- `classification_service.priority_score` — `+10` when `affects_academics` is truthy.
  (`submit` includes it in the `g_seed` dict.)
- `validation_service._DESC_MAX = 300`.
- Faculty routes added to `blueprints/faculty/__init__.py`:
  - `GET /profile` — own name/department/contact + change-PIN form.
  - `POST /profile/pin` — verify current PIN, set new (4-8 digits), `audit.add`.
- `app.py` context processor: for a logged-in reporter, compute `bell_dot` (True
  if any of their grievances has `updated_at` within 72h and status not
  `reported`). Wrapped in try/except; never breaks a render.
- Faculty home passes 3 pulse domains (electrical, water, cleanliness) as
  `campus_health` for the health pills.
- `auth` blueprint: login form `remember` checkbox → refresh token + cookie get a
  30-day lifetime instead of 7.
- Admin `templates/admin/detail.html` surfaces the two new fields read-only
  (no other admin change this pass).

## Frontend

- `static/css/app.css` — rebuilt as tokens + components (see plan Task 1). One file.
- `static/js/report.js` — rebuilt: camera step + sub-stepped details + review.
- `templates/base_faculty.html` — header (logo · title · bell · avatar), 5-item
  bottom nav (Home / Report / My Reports / Notices / Profile), PWA bits kept.
- `templates/faculty/{login,home,report,my_reports,grievance_detail,notices,profile}.html`
  — restyled to the mockup within the restrained palette.
- Every existing element `id`, form field name, route, and JSON shape the tests and
  backend depend on is preserved. Tests stay green (with additive edits only).

## Screen map (mockup → build)

1 Login · 2 Home · 3 Camera · 4 Photo captured · 6 Location+Priority ·
7 Description+noticed+affects · 8 Review · 9 Submitted · 10 My Reports ·
(+ Detail, Notices, Profile).

## Non-goals this pass

Admin portal restyle, admin charts, web-scalable (desktop) layout, push
notifications, offline photo queue.
