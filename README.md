# UNIFIX — GL Bajaj Campus Infrastructure Intelligence

Employees report campus infrastructure problems from their phone; a single Super
Admin ("Sir") reviews, routes, tracks and verifies every grievance. The system
turns individual reports into a live picture of infrastructure health, recurring
failures and maintenance priorities.

**Report → Understand → Prioritize → Assign → Resolve → Verify → Learn**

## Run it (development)

```bash
python -m pip install -r requirements.txt
python app.py                 # dev server on http://localhost:5000
```

Config is read from a gitignored `.env` in the project root (loaded via
python-dotenv). With no `DATABASE_URL` the dev server runs **in-memory** (data
lost on restart) — fine for local work; it logs a warning so you know. The
variables the app reads: `APP_ENV`, `SECRET_KEY`, `JWT_SECRET`, `DATABASE_URL`,
`FIREBASE_SERVICE_ACCOUNT_JSON` / `GOOGLE_APPLICATION_CREDENTIALS` /
`FIREBASE_KEY_JSON` / `FIREBASE_CREDENTIALS_B64` (+ `ALLOW_FIRESTORE_IN_DEV`),
`GROQ_API_KEY` / `GROQ_MODEL_TEXT` / `GROQ_MODEL_VISION`, `RESEND_API_KEY` /
`RESEND_FROM` / `ADMIN_ALERT_EMAIL`, `R2_*` or `AWS_*`/`S3_BUCKET_NAME` for
evidence-photo storage, `INITIAL_ADMIN_USERNAME` / `INITIAL_ADMIN_PIN` (prod
bootstrap), `TWA_PACKAGE_NAME` / `TWA_SHA256_CERT_FINGERPRINTS` (Android),
`SEED_DEMO`, `ALLOW_PROD_DEMO_SEED`, `PORT`, `FLASK_DEBUG`.

## Deploy it (production)

Production is `APP_ENV=production`. It is strict on purpose and **will refuse to
start** unless the environment is safe:

| Requirement | Why |
|---|---|
| `SECRET_KEY`, `JWT_SECRET` set, ≥ 32 chars, not a default | session / JWT forgery protection |
| `DATABASE_URL` set and reachable | PostgreSQL is the primary store; there is **no** silent in-memory fallback in production |
| `INITIAL_ADMIN_USERNAME` + `INITIAL_ADMIN_PIN` (first deploy only) | no automatic `admin`/`0000` in production; the seeded admin must change its PIN on first login |

If PostgreSQL is down and a Firestore fallback is configured, the app runs on
Firestore and logs that it has entered fallback mode. If **neither** is
available, the app exits loudly rather than pretend to work.

Demo/sample data is never seeded into a production database unless
`ALLOW_PROD_DEMO_SEED=1` is explicitly set.

```bash
gunicorn wsgi:app             # see Procfile
```

### Database provider (important on free tiers)

The app connects to Postgres at boot and then acquires a fresh connection per
request. Providers that **auto-suspend an idle database** are a bad fit: a
low-traffic pilot is idle most of the time, so nearly every request pays a
cold-start and many time out (`psycopg_pool.PoolTimeout`), which surfaces as
intermittent HTTP 500s and reports that never reach the admin queue.

- **Neon free tier** suspends compute after ~5 minutes idle and caps monthly
  compute hours — avoid for a live deployment.
- **Supabase free tier** stays warm (pauses only after ~7 days of *zero*
  activity) and has no compute-hour cap — recommended. This app is a persistent
  gunicorn server with its own connection pool, so use the **Session pooler**
  string (host `aws-0-<region>.pooler.supabase.com`, port `5432`, user
  `postgres.<project-ref>`) and append `?sslmode=require`. (The Transaction
  pooler on `6543` also works — the pool sets `prepare_threshold=None`.)
- A small **always-on paid instance** (Render/Neon/Supabase, ~$7/mo) is the
  robust option once the pilot proves out.

### Deploy on Render (checklist)

Set these in the Render dashboard → service → **Environment** (never commit a
`.env`):

| Var | Value |
|---|---|
| `APP_ENV` | `production` |
| `DATABASE_URL` | Supabase session-pooler URL (port `5432`) + `?sslmode=require` |
| `SECRET_KEY` | 40+ random chars |
| `JWT_SECRET` | 40+ random chars (different from `SECRET_KEY`) |
| `INITIAL_ADMIN_USERNAME` / `INITIAL_ADMIN_PIN` | first deploy only; PIN must be changed on first login |
| `GROQ_API_KEY`, `RESEND_API_KEY`, `RESEND_FROM` | as before |

Tables and the GL Bajaj location tree are created automatically on first boot.
Confirm success in the logs: `UNIFIX starting — env=production, db=postgres`.

## Accounts

**Development** seeds these automatically:

| Role | Username | PIN |
|---|---|---|
| Super Admin | `admin` | `0000` |
| Employee | `prof.rao`, `dr.iyer`, `prof.khan`, `prof.sharma` | `1234` |

**Production** has no default accounts — the first admin comes from
`INITIAL_ADMIN_*`. The admin creates further accounts at `/admin/users`.

### Admin tiers

The MVP has a single admin tier: every `admin` can perform every admin action,
including creating other admins (whitelisted role, audited as `admin.create`).
This is a deliberate decision for a one-coordinator campus — see `domain/rbac.py`.

## Demo data

```bash
SEED_DEMO=1 python scripts/seed_demo.py   # dev/test only; ~35 grievances,
                                          # recurring "Room 204 projector", Block B gaps
```

## Tests

```bash
python -m pytest        # in-memory backend, no external services
```

## Campus locations

Locations are a real tree the admin maintains at **`/admin/locations`**:

```
GL Bajaj campus
 ├── AB1 / AB2 (building) → Floor → Room (+ room type)
 ├── B.Tech / MBA / BCA Canteen, Library, SHD Hall, Medical Facility → (specific area)
 ├── Hostels, Playground
 └── Outer Area → sub-zone
```

Only **verified** structure is seeded (AB1, AB2, the named facilities). **No room
numbers are invented** — enter the real GL Bajaj room list at `/admin/locations`;
no code change or redeploy needed. A reporter picks a node in the report wizard;
if a room isn't catalogued yet they pick the floor and type the number. Each
grievance stores both the `location_id` and the flat building/floor/room/facility
fields, so existing reports never break and the admin queue can filter by any of
them.

## Android / Google Play

UNIFIX ships to Play as a **Trusted Web Activity** (no native rewrite). See
`android/README.md` for the build, and `docs/GOOGLE_PLAY_READINESS.md` for the
full A–G readiness checklist, `docs/PLAY_DATA_SAFETY.md`, and
`docs/PLAY_STORE_LISTING.md`.

## Layout

```
app.py / wsgi.py / config.py   Flask app factory + config + startup validation
db/          persistence — PostgreSQL primary → Firestore fallback → in-memory (dev only)
domain/      constants, dataclasses, RBAC permission map
services/    auth · grievance pipeline · classification · duplicate/recurring ·
             intelligence (KPIs/Pulse/Gaps/analytics) · notifications · storage
ai/          Groq client + campus prompts (optional)
blueprints/  public (privacy, /.well-known)  ·  auth  ·  faculty (PWA)  ·  admin
templates/ static/   Jinja + vanilla JS, PWA manifest + service worker + icons
scripts/     make_icons.py · seed_demo.py
android/     Trusted Web Activity packaging (Bubblewrap)
docs/        deployment phases · Google Play readiness · data safety · store listing
```
