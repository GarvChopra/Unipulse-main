# UniPulse — GL Bajaj Campus Infrastructure Intelligence

Faculty report campus infrastructure problems from their phone; a single Super
Admin ("Sir") reviews, routes, tracks and verifies every grievance. The system
turns individual reports into a live picture of infrastructure health, recurring
failures and maintenance priorities.

**Report → Understand → Prioritize → Assign → Resolve → Verify → Learn**

## Run it

```bash
python -m pip install -r requirements.txt
cp .env.example .env          # optional — the app runs fully without it

python app.py                 # dev server on http://localhost:5000
# or: gunicorn wsgi:app       # production (set DATABASE_URL, SECRET_KEY, JWT_SECRET)
```

With no `DATABASE_URL` the app runs **in-memory** (data lost on restart) — fine for
a demo. Set `DATABASE_URL` (Postgres / Neon) to persist.

Optional env vars (each feature degrades gracefully when unset):
`GROQ_API_KEY` (AI classification → keyword fallback otherwise),
`RESEND_API_KEY` + `ADMIN_ALERT_EMAIL` (email notifications → no-op otherwise),
`IMAGEKIT_PRIVATE_KEY` (photo storage → inline data-URI otherwise).

## Demo data

```bash
python scripts/seed_demo.py    # needs DATABASE_URL to persist; seeds ~10 grievances,
                               # a recurring "Room 204 projector" issue, and Block B gaps
```

## Accounts (seeded)

| Role | Username | PIN |
|---|---|---|
| Super Admin | `admin` | `0000` |
| Faculty | `prof.rao`, `dr.iyer`, `prof.khan`, `prof.sharma` | `1234` |

The admin creates further faculty accounts at `/admin/users`.

## Tests

```bash
python -m pytest        # 135 tests, in-memory backend, no external services
```

## Layout

```
app.py / wsgi.py / config.py   Flask app factory + config
db/          persistence — Postgres primary, in-memory fallback (same dict shapes)
domain/      constants, dataclasses, RBAC permission map
services/    auth · grievance pipeline · classification · duplicate/recurring ·
             intelligence (KPIs/Pulse/Gaps/analytics) · notifications · storage
ai/          Groq client + campus prompts (optional)
blueprints/  auth  ·  faculty (PWA)  ·  admin (/admin/*, RBAC)
templates/ static/   Jinja + vanilla JS, PWA manifest + service worker
scripts/     make_icons.py · seed_demo.py
docs/superpowers/   design spec + phase-by-phase implementation plans
```

Built as phases 0–E (see `docs/superpowers/plans/`); every phase is green.
