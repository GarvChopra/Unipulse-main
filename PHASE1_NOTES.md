# Phase 1 — Backend fork & strip

Fork of `../areapulse-2` (github.com/shash-shukla06/Areapulse) into `unipulse-campus/`.
App boots and serves in memory mode; functional smoke test passes (login, /areas,
/locations, /report, /issues, /stats, admin /gov placeholder; all /ngo/* → 404).

## 1. Files copied

The reference is **not** four flat files — `app.py` imports `domain/`, `services/`
(10 modules), `repositories/` (3), plus `email_sender.py`. Copied the whole
importable backend + `templates/`, `static/`, `models/spam_clf.pkl`,
`requirements.txt`, `Procfile`, `nixpacks.toml`, `.gitignore`. Did **not** copy the
reference's `.git`, its `*.md` design docs, `train_spam_model.py`, or `models/archived/`.

## 2. NGO — fully removed

| File | Change |
|---|---|
| `app.py` | Deleted routes `/ngo/all`, `/ngo/nearby`, `/ngo/dashboard`, `/ngo/commit`, `/ngo/ai-recommendations`; deleted `NGO_ACCOUNTS`, `_ngo_commitments_store`, `_ap_compute_opportunities()`, `/gov/all` + `_GOV_LOCATIONS`/`_GOV_ICONS` (NGO "Govt Agencies" tab feed). `/ngo/escalate/<id>` → renamed `/issue/<id>/escalate` (kept the handler). `issue_detail` no longer computes `nearby_ngos` (returns `[]`). `firestore_health` no longer counts `ngos`. |
| `database.py` | Dropped `ngos` + `ngo_commitments` tables, their indexes and `ALTER`s from the schema DDL; removed `get_all_ngos()`, `get_nearby_ngos()`, `_ngo_row_to_dict()`, `_state['ngos']`. |
| `domain/models.py` | Deleted `NGO` dataclass; removed `UserRole.NGO_MANAGER`; removed `AuthUser.org_name` / `operating_areas` / `is_ngo()`. |
| `services/auth_service.py` | `login()` / `refresh_access_token()` drop the `ngo_accounts` param and NGO branch; JWT payload no longer carries `org_name` / `operating_areas`. |
| `services/issue_service.py` | Removed `AbstractNGORepository` dep, `_ngo_repo`, the `configure(ngo_repo=…)` param, and the post-insert `get_nearby()` call; `_ok()` no longer returns `nearby_ngos`. |
| `repositories/` | Deleted `AbstractNGORepository` (interfaces) and `DatabaseNGORepository` (database_repository); `user_repository` lost `get_ngo_account()` and its half of `seed_demo_accounts()`. |
| `templates/` | Deleted `ngos.html`; rebuilt `login.html` to two roles (Faculty / Super Admin) — removed the NGO + external-Gov-portal tabs. |

## 3. Roles → `reporter` / `admin`

- `UserRole` is now just `REPORTER = 'reporter'` and `ADMIN = 'admin'` (values kept
  generic so a 2nd admin can be added with no schema change — per CLAUDE.md & MVP plan §14).
- `GOV_ACCOUNTS` (4 Delhi dept officers) → `ADMIN_ACCOUNTS` = one `admin` account
  (`Super Admin`, PIN `0000`, empty `tags` = sees every category).
- Session key `gov_role` → `admin_role`; `is_gov()` → `is_admin()` everywhere;
  `ngo_role` session key gone.
- Google OAuth users are now issued the `reporter` role.
- `users.role` DB comment updated to `'reporter' | 'admin'`; the `get_admin_account`
  query filters `role = 'admin'`.

## 4. Campus locations (replaces Delhi geography)

- `domain/constants.py`: the 36-entry Delhi `AREA_COORDS` is replaced by campus data:
  `CAMPUS_LOCATION_TYPES` (5), `OUTER_AREA_SUBZONES` (5), `CAMPUS_AREAS` (flat
  selectable list). `AREA_COORDS` is kept **as a name** for import compatibility but
  every value is `(None, None)` — there is no GPS in this MVP, so the coordinate-resolve
  and geo-dedup paths downstream short-circuit on `if lat and lng`.
- `DELHI_LAT/LNG_MIN/MAX` → `GEO_*` (whole-Earth permissive bounds; old names kept as aliases).
- New **`locations`** table (Postgres) + memory seed, columns matching MVP plan §14:
  `location_type, block_no, floor, room, sub_zone, name, full_path, lat, lng, is_active,
  parent_id`. `seed_locations()` runs on every boot (idempotent). Seeds the 5 top-level
  types + 5 Outer Area sub-zones = **10 rows**. Academics Block → Block/Floor/Room
  drill-down is **not** seeded (real counts unknown — that's the Phase 2 picker).
- New getter `get_locations(type=…)` and route `GET /locations` (feeds the Phase 2 picker).
- `get_areas()` now derives from seeded locations, falling back to `KNOWN_AREAS`.

## 5. Things I was unsure how to adapt — need your call

1. **The reference has no `/gov` dashboard template.** In this fork of AreaPulse the
   gov & NGO dashboards were moved to *separate external portal repos*; `templates/`
   only has the citizen-facing pages. CLAUDE.md Phase 3 says "adapt the `/gov`
   template" — there is nothing to adapt. `/gov` is currently a one-line placeholder;
   Phase 3 builds the admin queue fresh on the `base.html` shell.
2. **The reference frontend IS a Leaflet map** (`templates/index.html`, `/` route).
   CLAUDE.md says "no map". I left `index.html` untouched for Phase 1 (backend only) —
   it still renders a Delhi map and calls now-dead `/ngo/*` endpoints (guarded by
   `.catch()`, so it degrades rather than breaks). Phase 2/3 replaces this frontend.
3. **`ai_engine.py` left completely as-is** (CLAUDE.md: "reuse as-is, swap category
   list only"). Its prompts still say "Delhi / civic / citizen" and it classifies into
   the old 10 civic tags. The category swap (Electric/Plumbing/Civil/Mechanical/Power/
   IT-Network) + campus-tuned prompts is a later step — `classifier.py`, `IssueTag`,
   and `SLA_HOURS` are still the civic set.
4. **`IssueStatus` unchanged** (`open/acknowledged/in_progress/resolved/escalated`),
   including the Postgres `CHECK` constraint. The campus workflow
   (`Reported → Verified → Assigned → In Progress → Resolved → Admin Verified → Closed`)
   and the "Resolved requires evidence" rule are Phase 3.
5. **WhatsApp inbound bot** (`/whatsapp`) and the **community feed seed** still contain
   Delhi place-names and civic copy. Not in campus MVP scope — flag for removal or
   rework later.
6. **`Campus` entity** (MVP plan §14, multi-tenant) not built — `locations.campus` is
   just a `'Main Campus'` text default for now.
7. Grievance IDs still come from the DB sequence as bare integers; the `AP-CAMP-00001`
   format is Phase 2.
8. `update_issue_status` still merges the audit entry as `status_history` JSON — fine,
   but the richer `Timeline` / `Assignment` / `Evidence` entities (MVP plan §14) are Phase 3.

## Smoke test

`GET /login /  /areas /locations` → 200 · `POST /login` (admin→`/gov`, faculty→`/`) →
302 · `POST /report` → `{"status":"ok","id":1,...}` · `GET /issues /my-issues-data
/stats` → 200 · `GET /ngo/all /ngo/dashboard` → 404. Runs in in-memory mode (no
`DATABASE_URL`); Postgres schema path not exercised here but DDL is syntactically
consistent with the reference's.

---
**Superseded 2026-08-30.** The project was re-scoped to the full campus MVP. See
`docs/superpowers/specs/2026-08-30-unipulse-campus-design.md` and the plans under
`docs/superpowers/plans/`. Phase-0+A restructured this fork into an app-factory
layout; the NGO/role/location decisions from this note still hold.
