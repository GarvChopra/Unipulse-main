# UNIFIX — Play Store listing content

Draft copy + the asset checklist for the Play Console store-listing page.
Institute to review wording and branding before publishing.

## Text

**App name** (30 chars max)
```
UNIFIX
```

**Short description** (80 chars max)
```
Report and track campus infrastructure issues at GL Bajaj.
```

**Full description** (4000 chars max)
```
UNIFIX is the campus infrastructure reporting system for GL Bajaj Institute of
Technology & Management.

Staff use UNIFIX to report problems with campus facilities — electrical,
plumbing, civil, mechanical, power and IT/network — straight from their phone:
take a photo, choose the exact location (building, floor, room or facility),
describe the problem, and submit. The campus administration reviews every
report, confirms the category, routes it to the responsible team, tracks it to
completion and verifies the fix with an "after" photo before closing it.

UNIFIX turns individual reports into a live picture of campus infrastructure —
which areas need attention, which problems keep recurring, and where maintenance
effort should go.

Features
• One-tap issue reporting with photo and structured location
• Automatic category and priority suggestion
• Live status tracking of your reports
• Recurring-issue detection (many reports of the same problem are grouped)
• Campus notices
• For administrators: a full triage queue, SLA tracking, assignment to
  responsible units, resolution evidence, an audit trail and campus-health
  analytics

Access
UNIFIX accounts are created by the campus administrator. There is no public
sign-up. This app is intended for GL Bajaj staff.

Privacy
UNIFIX does not use your device location, does not contain ads, and contains no
advertising or analytics trackers. See the privacy policy for details.
```

**App category**: Productivity
**Tags**: productivity, utilities
**Contact email**: <institute email>
**Website**: https://<host>/
**Privacy policy**: https://<host>/privacy

## Assets checklist

| Asset | Spec | Status | Source |
|---|---|---|---|
| App icon | 512×512 PNG, 32-bit | ✅ | `static/icons/icon-512.png` |
| Feature graphic | 1024×500 PNG/JPG, no transparency | ⬜ to create | design team — crest + "UNIFIX" wordmark on navy |
| Phone screenshots | ≥2, 16:9 or 9:16, 320–3840 px | ⬜ to capture | run the app on a phone / emulator: (1) report wizard, (2) my reports, (3) admin queue, (4) report detail |
| 7-inch tablet screenshots | optional | ⬜ | optional |
| 10-inch tablet screenshots | optional | ⬜ | optional |
| Promo video | optional | ⬜ | skip for v1 |

Screenshots referenced by the web manifest live at `static/screenshots/`
(`report.png`, `admin.png`) — capture them at 1080×1920 and drop them there;
they also feed the browser "richer install UI".

## Release notes (v1.0.0)
```
First release of UNIFIX for GL Bajaj.
Report campus infrastructure issues with a photo and exact location, and track
them through to a verified fix.
```

## Countries / regions
India (expand later if needed). Consider **Internal / unlisted** distribution if
the app should not be publicly discoverable.
