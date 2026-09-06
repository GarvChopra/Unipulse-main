"""Domain constants for UNIFIX (GL Bajaj campus). Stdlib-only."""

CATEGORIES = ["Electric", "Plumbing", "Civil", "Mechanical", "Power", "IT / Network"]
SEVERITIES = ["low", "medium", "high"]

STATUSES = ["reported", "verified", "assigned", "in_progress",
            "resolved", "admin_verified", "closed"]

STATUS_TRANSITIONS = {
    "reported":       ["verified"],
    "verified":       ["assigned"],
    "assigned":       ["in_progress"],
    "in_progress":    ["resolved"],
    "resolved":       ["admin_verified", "in_progress"],   # in_progress = reopen
    "admin_verified": ["closed", "in_progress"],           # in_progress = reopen
    "closed":         [],
}

RESPONSIBLE_UNITS = {
    "College":   ["Infrastructure", "Sanitation", "Housekeeping", "Landscaping", "Mess", "Parking"],
    "Academics": ["Class", "Lab"],
}
RESPONSIBLE_UNITS_FLAT = RESPONSIBLE_UNITS["College"] + RESPONSIBLE_UNITS["Academics"]

# Coarse location "buckets" — copied onto grievance.location_type so the
# intelligence layer, validation and duplicate detection keep working while the
# reporter picks a precise node from the location tree.
LOCATION_TYPES = [
    {"key": "academics_block", "name": "Academics Block", "drilldown": True},
    {"key": "hostels",         "name": "Hostels",         "drilldown": False},
    {"key": "mess_canteen",    "name": "Mess / Canteen",  "drilldown": True},
    {"key": "playground",      "name": "Playground",       "drilldown": False},
    {"key": "outer_area",      "name": "Outer Area",       "drilldown": True},
    {"key": "facility",        "name": "Campus Facility",  "drilldown": True},
]
LOCATION_BUCKETS = [t["key"] for t in LOCATION_TYPES]

OUTER_AREA_SUBZONES = ["Common/Electrical", "Security", "Lawn Area", "Sewage", "Drainage"]

# ── Verified GL Bajaj campus structure ────────────────────────────────────
# Only what public sources / the GL Bajaj website confirm. NO invented room or
# floor numbers — the admin adds the real room list at /admin/locations later
# without any code change.
CAMPUS_NAME = "GL Bajaj Institute of Technology & Management"
# Public sources identify the two academic blocks as AB1 and AB2.
CAMPUS_BUILDINGS = ["AB1", "AB2"]
# Generic structural floor levels — scaffolding only; the admin enables/renames
# per building and adds rooms beneath them.
BUILDING_FLOORS = ["Ground Floor", "1st Floor", "2nd Floor", "3rd Floor", "4th Floor"]
# Standalone facilities. Canteens route to the Mess unit; the rest are generic.
CAMPUS_CANTEENS = ["B.Tech Canteen", "MBA Canteen", "BCA Canteen"]
CAMPUS_FACILITIES = ["Library", "SHD Hall", "Medical Facility"]
# Room types the admin can tag a room with.
ROOM_TYPES = ["Classroom", "Lab", "Faculty Room", "Office",
              "Washroom", "Store", "Other Facility"]

# Back-compat aliases (older modules/tests import these names).
ACADEMICS_BLOCKS = CAMPUS_BUILDINGS
ACADEMICS_FLOORS = BUILDING_FLOORS

SLA_HOURS = {
    "Electric": 24, "Power": 24, "Plumbing": 48,
    "Mechanical": 72, "Civil": 120, "IT / Network": 48,
}

PULSE_DOMAINS = [
    {"key": "electrical",  "name": "Electrical",       "categories": ["Electric", "Power"], "location_type": None,              "sub_zone": None},
    {"key": "water",       "name": "Water / Plumbing", "categories": ["Plumbing"],          "location_type": None,              "sub_zone": None},
    {"key": "classrooms",  "name": "Classrooms",       "categories": [],                    "location_type": "academics_block", "sub_zone": None},
    {"key": "it",          "name": "IT",               "categories": ["IT / Network"],      "location_type": None,              "sub_zone": None},
    {"key": "cleanliness", "name": "Cleanliness",      "categories": ["Civil"],             "location_type": None,              "sub_zone": None},
    {"key": "security",    "name": "Security",         "categories": [],                    "location_type": None,              "sub_zone": "Security"},
]

RECURRING_WINDOW_DAYS = 14
GAP_THRESHOLD = 4
HIGH_PRIORITY_ALERT = 60   # new grievance at/above this priority (or severity high) alerts the admin
CODE_PREFIX = "GLB-CAMP-"
CODE_PAD = 5

GLB = {
    "name": "GL Bajaj Institute of Technology and Management",
    "short": "GL Bajaj",
    "product": "UNIFIX",
    "email_domain": "glbitm.ac.in",
    "theme_navy": "#0b2a5b",
    "theme_blue": "#1e5fbf",
}
