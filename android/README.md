# UNIFIX — Android (Trusted Web Activity) package

UNIFIX ships to Google Play as a **Trusted Web Activity (TWA)**: a thin Android
shell that opens the production UNIFIX PWA full-screen, with no browser UI. There
is **no native rewrite** — the entire app (login, reporting, admin portal, AI
classification, workflow) is the same web app, served from the production host.

```
Production UNIFIX PWA  →  TWA shell (this folder)  →  signed .aab  →  Play Console
```

## Prerequisites (on the build machine — not this repo's CI yet)

| Tool | Version |
|---|---|
| Node.js | ≥ 18 |
| JDK | 17 (Temurin) |
| Android SDK command-line tools | latest; `platforms;android-36`, `build-tools;36.0.0` |
| Bubblewrap CLI | `npm i -g @bubblewrap/cli` |

Set `JAVA_HOME` and `ANDROID_HOME` before running Bubblewrap.

## One-time setup

1. **Deploy UNIFIX to its production HTTPS host first.** TWA + Digital Asset
   Links are bound to a fixed origin. Note the host (e.g. `unifix.glbitm.ac.in`).

2. Fill in the host in `twa-manifest.json` — replace every
   `REPLACE_WITH_PRODUCTION_HOST` with the real host (no scheme).

3. Generate the Android project:

   ```bash
   cd android
   bubblewrap init --manifest ./twa-manifest.json      # first time
   # or, if twa-manifest.json already exists and you edited it:
   bubblewrap update
   ```

4. **Signing key** — create the upload key once and keep it safe (losing it means
   you can never update the app):

   ```bash
   keytool -genkey -v -keystore android.keystore -alias unifix \
     -keyalg RSA -keysize 2048 -validity 10000
   ```

   Get its SHA-256 fingerprint:

   ```bash
   keytool -list -v -keystore android.keystore -alias unifix | grep SHA256
   ```

5. **Digital Asset Links** — put that fingerprint (and, after you enrol in Play
   App Signing, the Play signing-key fingerprint too) into the server
   environment:

   ```
   TWA_PACKAGE_NAME=in.ac.glbitm.unifix
   TWA_SHA256_CERT_FINGERPRINTS=AB:CD:...,  12:34:...
   ```

   The server then serves them at
   `https://<host>/.well-known/assetlinks.json` (route already implemented in
   `blueprints/public`). Verify with:
   <https://developers.google.com/digital-asset-links/tools/generator>

## Build the release bundle

```bash
cd android
bubblewrap build            # produces app-release-bundle.aab  (+ app-release-signed.apk)
```

`bubblewrap build` will also print the SHA-256 of the key it signed with — it
must match what `/.well-known/assetlinks.json` serves, or the app opens with a
URL bar.

## Upload

1. Play Console → **Create app** → app name **UNIFIX**, category *Productivity*,
   not free-to-contain-ads.
2. **App bundle** → upload `app-release-bundle.aab` to the **Internal testing**
   track first.
3. Enrol in **Play App Signing** (recommended). Copy the *App signing key*
   SHA-256 that Play shows you and **add it to
   `TWA_SHA256_CERT_FINGERPRINTS`** alongside the upload key, then redeploy the
   server.
4. Complete the Play Console declarations — see
   `../docs/GOOGLE_PLAY_READINESS.md` (sections D & E) and
   `../docs/PLAY_DATA_SAFETY.md`.
5. Add internal testers, roll out to Internal testing, verify the checklist in
   `../docs/GOOGLE_PLAY_READINESS.md` section F on a real device, then promote to
   Closed → Open/Production.

## What the shell does and does not do

- **Does**: full-screen the PWA, map the Android back button to web history,
  keep the session (cookies persist in the TWA's Chrome profile), pass through
  camera permission prompts, show a splash from the manifest icon + background.
- **Does not**: store data itself, contain business logic, embed URLs or keys —
  it only knows the production host. Everything else is the web app.

## Files

| File | Purpose | Commit? |
|---|---|---|
| `twa-manifest.json` | Bubblewrap config (host must be filled in) | yes |
| `android.keystore` | signing key | **NO — never commit** (see `.gitignore`) |
| `app-release-bundle.aab`, `app/`, build output | generated | no |
