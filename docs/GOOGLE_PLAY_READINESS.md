# UNIFIX — Google Play Readiness Audit

Prepared for the deployment handover. UNIFIX ships as a **Trusted Web Activity**
wrapping the existing production PWA — no native rewrite. This document is the
checklist from "code as it is now" to "app live on Google Play".

Status legend: ✅ done in this repo · 🔧 code change still needed · ⚙️ Android/Play
config · 📄 Play Console data entry · ⚖️ privacy/legal · 🧪 testing · ⛔ blocker.

---

## A. Already ready

| Item | Where |
|---|---|
| ✅ Full PWA: manifest, service worker, offline page, installable | `static/manifest.webmanifest`, `static/service-worker.js`, `/offline` |
| ✅ Manifest has `id`, `name`, `short_name`, `start_url`, `scope`, `display:standalone`, `orientation`, `theme_color`/`background_color` (aligned to `#0e2f5c`), `categories`, maskable icons declared | `static/manifest.webmanifest` |
| ✅ Real launcher icons (GL Bajaj crest on navy) — `icon-192/512`, `maskable-192/512` | `static/icons/`, regenerate via `scripts/make_icons.py` |
| ✅ `/.well-known/assetlinks.json` served from env (`TWA_PACKAGE_NAME`, `TWA_SHA256_CERT_FINGERPRINTS`) | `blueprints/public/__init__.py` |
| ✅ In-app Privacy Policy + Account/Data Deletion pages, linked from login, profile, admin | `/privacy`, `/account-deletion`, `templates/public/` |
| ✅ In-app account deletion flow (reporter self-serves; admin de-identifies reports) | `/profile/delete`, `/admin/users/<id>/delete` |
| ✅ Android hardware **back button** walks the report wizard steps (history state per step) | `static/js/report.js` |
| ✅ Session survives app backgrounding: expired access token auto-refreshes from the refresh cookie server-side | `app.py::_load_user` |
| ✅ Deactivation / role change / PIN reset take effect on the next request (no 15-min stale window) | `app.py::_load_user` |
| ✅ Camera used only on demand (`getUserMedia` + `<input capture>`); **no geolocation permission** anywhere | `static/js/report.js` |
| ✅ Evidence photos downscaled client- and server-side (≤1600px JPEG) — no 16 MB upload failures | `static/js/report.js`, `services/storage_service.py` |
| ✅ All API calls are same-origin relative paths — nothing to reconfigure for the TWA | app-wide |
| ✅ No hardcoded localhost / dev URLs / secrets in application code (only in gitignored `.env`) | verified |
| ✅ Production config is fail-loud (weak secrets, missing DB, no admin → refuses to start) | `config.py`, `db/pool.py`, `db/seeds.py` |
| ✅ Android TWA project + build instructions | `android/` |
| ✅ `requirements.txt` now complete (`Pillow`, `boto3`, `firebase-admin` were imported but missing) | `requirements.txt` |

---

## B. Needs code changes

| # | Item | Effort |
|---|---|---|
| 🔧 B1 | **Object storage for evidence photos.** Code + deps are in place (`storage_service` R2/S3), but with no `R2_*`/`S3_*` env set the app stores photos as base64 in the DB. Downscaling makes this survivable for a pilot; a full rollout should set Cloudflare R2. The app now logs a startup warning in production when unset. | config only, or ~0 code |
| 🔧 B2 | **PostgreSQL path has no automated test.** A schema-consistency guard was added (`tests/test_schema_consistency.py`), but the SQL in `db/*.py` is still only exercised in-memory. Run the E2E once against a real Postgres (Neon branch / local) before go-live. | 1–2 h manual |
| 🔧 B3 | **Firestore fallback** — dependency now shipped and credential-var names reconciled (`FIREBASE_KEY_JSON` / `FIREBASE_SERVICE_ACCOUNT_JSON` / `GOOGLE_APPLICATION_CREDENTIALS` / base64). Still unverified against a live Firestore project. Decide: verify it, or drop it and rely on Postgres HA. | 1 h or delete |
| 🔧 B4 | **Login rate-limiter is per-process** → `Procfile` pins `--workers 1`. Fine for a campus pilot; move to a shared store (Postgres table / Redis) before scaling workers. | 2–3 h, not blocking |
| 🔧 B5 | **Offline report drafts** — `/offline` says drafts are kept; they are not. Either persist the wizard form to `localStorage`, or soften the copy. | 2 h or 5 min |
| 🔧 B6 | **CSRF tokens** on admin POST forms. Mitigated today by `SameSite=Strict` cookies; add tokens for defence in depth. | 3 h, not blocking |

---

## C. Needs Android configuration

| # | Item |
|---|---|
| ⚙️ C1 | Deploy UNIFIX to its **production HTTPS host**; put the host in `android/twa-manifest.json` (replace `REPLACE_WITH_PRODUCTION_HOST`). |
| ⚙️ C2 | `bubblewrap init --manifest ./twa-manifest.json` then `bubblewrap build` on a machine with JDK 17 + Android SDK (`platforms;android-36`). Targets **API 36** (set in the manifest). |
| ⚙️ C3 | Create the **upload signing key** (`keytool`, see `android/README.md`); store it in a password manager / secure vault. Losing it = cannot update the app. |
| ⚙️ C4 | Put the key's SHA-256 into `TWA_SHA256_CERT_FINGERPRINTS` on the server and redeploy, so `/.well-known/assetlinks.json` verifies. After enrolling in Play App Signing, **add Play's signing-key SHA-256 too**. |
| ⚙️ C5 | Package id is **`in.ac.glbitm.unifix`** (unique, reverse-DNS of the institute). Confirm the institute is OK with this id — it can never change once published. |
| ⚙️ C6 | App version: `appVersionName 1.0.0`, `appVersionCode 1` — bump `appVersionCode` every upload. |

---

## D. Needs Play Console information

| # | Item | Value / source |
|---|---|---|
| 📄 D1 | App name | **UNIFIX** |
| 📄 D2 | Short description (≤80 chars) | see `docs/PLAY_STORE_LISTING.md` |
| 📄 D3 | Full description | see `docs/PLAY_STORE_LISTING.md` |
| 📄 D4 | App icon (512×512), feature graphic (1024×500), ≥2 phone screenshots | icon = `static/icons/icon-512.png`; feature graphic + screenshots: **to be produced** (screenshots can be captured from the running app — `static/screenshots/`) |
| 📄 D5 | App category | Productivity |
| 📄 D6 | Contact email / website | institute email + `https://<host>/privacy` |
| 📄 D7 | Privacy policy URL | `https://<host>/privacy` |
| 📄 D8 | **App access** — Play reviewers cannot self-register. Provide a test **reporter** account and a test **admin** account (username + PIN) in *App access* → "All or some functionality is restricted". Create them via `/admin/users` on the production instance (or a dedicated review instance). |
| 📄 D9 | Content rating questionnaire | No violence / sexual / gambling content → expected rating: **Everyone / PEGI 3**. It is a utility app with user-generated photos (infrastructure only) + free-text; answer the UGC question truthfully (moderated by admin, reportable). |
| 📄 D10 | Target audience | Adults (institute staff); not designed for children. |
| 📄 D11 | Data safety form | see `docs/PLAY_DATA_SAFETY.md` |
| 📄 D12 | Ads declaration | **Contains no ads.** |
| 📄 D13 | Government app / financial / health declarations | None apply. |

---

## E. Needs privacy / legal preparation

| # | Item |
|---|---|
| ⚖️ E1 | **Institute review of the Privacy Policy** (`templates/public/privacy.html`) — confirm the legal entity name, the contact address (`PRIVACY_CONTACT_EMAIL` env, defaults to `unifix@glbitm.ac.in`), the data-retention statement, and whether Groq / Resend are actually enabled in production (the policy is written to cover both cases). |
| ⚖️ E2 | **Data Processing** — Groq (AI) and Resend (email) are third-party processors *only if their API keys are set*. If enabled, confirm the institute is comfortable that a report's **text + photo** leaves the country to Groq's API. If not acceptable, leave `GROQ_API_KEY` unset — the app falls back to on-server keyword classification with no external call. |
| ⚖️ E3 | Confirm the account-deletion policy: reports are **de-identified, not erased** (they document campus infrastructure history). Decide if that is acceptable or if full erasure-on-request is required. |
| ⚖️ E4 | Data retention period — the policy currently says "as long as needed for maintenance record-keeping". Set a concrete period if the institute has one. |
| ⚖️ E5 | If the app will be **unlisted / internal-only distribution**, note that in Play Console (Managed Google Play or Internal-only) — this reduces some store-listing requirements but Data Safety + Privacy Policy are still mandatory. |

---

## F. Needs testing (on a real Android device, via Internal Testing track)

| # | Check |
|---|---|
| 🧪 F1 | App installs from Play Internal Testing, opens **full-screen with no URL bar** (proves assetlinks verified). |
| 🧪 F2 | **Full reporter journey**: login → photo (camera + gallery) → location tree (building→floor→room / facility→area) → description → submit → appears in "My Reports" with correct status. |
| 🧪 F3 | **Full admin journey**: login → queue → filter by building/floor/room/facility → open report → verify → assign unit + SLA → in-progress → upload resolution photo+note → resolved → admin-verified → closed; dashboard + audit log reflect every step. |
| 🧪 F4 | **Employee lifecycle**: admin creates employee (dept + role) → employee logs in → blocked from `/admin` → admin deactivates → employee's open session is rejected on next action → admin resets PIN → employee forced through set-PIN. |
| 🧪 F5 | **Account deletion**: reporter deletes own account → logged out immediately → admin sees the request → completes de-identification → past reports show "Former staff". |
| 🧪 F6 | **Back button**: at wizard step 2/3, Android back returns to the previous step, not out of the app. |
| 🧪 F7 | **Network loss**: turn off wifi mid-session → offline page shows for navigations → reconnect → app recovers; a failed submit shows an error and can be retried. |
| 🧪 F8 | **Session persistence**: background the app 20+ min, reopen → still logged in (access token auto-refreshed). |
| 🧪 F9 | **Camera permission**: first photo prompts for camera; deny → gallery fallback still works. |
| 🧪 F10 | Large photo (12 MP) submits successfully and the stored/displayed image is downscaled. |
| 🧪 F11 | Rotate device — layouts hold on small and large screens. |
| 🧪 F12 | Recurring detection: two staff report the same room+category → admin queue shows one grouped row. |

---

## G. Blockers before production release

| # | Blocker | Owner |
|---|---|---|
| ⛔ G1 | **No production HTTPS host deployed.** Everything downstream (assetlinks, TWA, store URLs) needs it. | deployment team |
| ⛔ G2 | **Signing key not created / not in assetlinks.** Without it the TWA opens with a URL bar and fails review expectations. | deployment team (C3–C4) |
| ⛔ G3 | **Privacy Policy not institute-approved** and not yet at a public URL. Play blocks submission without it. | institute + deployment (E1) |
| ⛔ G4 | **Data Safety form not filled** in Play Console. Mandatory. Answers drafted in `docs/PLAY_DATA_SAFETY.md`. | deployment (D11) |
| ⛔ G5 | **Reviewer test credentials not provided** (App access). Play will reject a login-walled app without them. | deployment (D8) |
| ⛔ G6 | **PostgreSQL path unverified end-to-end** against a real database. Ship-stopper for data integrity, independent of Android. | deployment (B2) |
| ⛔ G7 | **Store listing assets** (feature graphic 1024×500, ≥2 screenshots) not produced. | deployment/design (D4) |

Not blockers but strongly recommended before a wide rollout: object storage (B1),
a second admin account for continuity, and the real GL Bajaj room list entered
under `/admin/locations`.
