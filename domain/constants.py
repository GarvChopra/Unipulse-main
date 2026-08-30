"""Domain constants for UniPulse (GL Bajaj campus). Stdlib-only."""

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

LOCATION_TYPES = [
    {"key": "academics_block", "name": "Academics Block", "drilldown": True},
    {"key": "hostels",         "name": "Hostels",         "drilldown": False},
    {"key": "mess_canteen",    "name": "Mess / Canteen",  "drilldown": False},
    {"key": "playground",      "name": "Playground",      "drilldown": False},
    {"key": "outer_area",      "name": "Outer Area",      "drilldown": True},
]
OUTER_AREA_SUBZONES = ["Common/Electrical", "Security", "Lawn Area", "Sewage", "Drainage"]
ACADEMICS_BLOCKS = ["Block A", "Block B", "Block C", "Block D"]
ACADEMICS_FLOORS = ["Ground Floor", "1st Floor", "2nd Floor", "3rd Floor", "4th Floor"]

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
    "product": "UniPulse",
    "email_domain": "glbitm.ac.in",
    "theme_navy": "#0b2a5b",
    "theme_blue": "#1e5fbf",
}
