"""Grievance classification (Groq + keyword fallback) and priority scoring."""
from __future__ import annotations

import time

from ai import engine
from domain.constants import CATEGORIES

KEYWORDS: dict[str, list[str]] = {
    "Electric":     ["light not", "lights not", "tubelight", "tube light", "light bulb",
                     "bulb", "light switch", "switchboard", "switch board", "power socket",
                     "wall socket", "wiring", "short circuit", "sparking", "spark from",
                     "ceiling fan", "fan not working", "fan is not working", "fan stopped",
                     "fan not spinning", "electrical fitting", "exposed wire", "live wire"],
    "Power":        ["power cut", "no power", "power outage", "power failure", "outage",
                     "generator", "inverter", "voltage", "load shedding", "mains tripped",
                     "mcb tripped", "breaker tripped", "electricity is gone", "no electricity"],
    "Plumbing":     ["water leak", "leaking water", "water is leaking", "tap is", "faucet",
                     "pipe burst", "pipe is", "burst pipe", "drain", "flush not",
                     "toilet", "washroom", "restroom", "wash basin", "basin", "sink",
                     "overflow", "sewage", "clogged", "blocked drain", "no water",
                     "water supply", "leakage"],
    "Civil":        ["wall crack", "ceiling crack", "cracked wall", "crack in", "paint peeling",
                     "door is broken", "door lock", "window pane", "broken window",
                     "floor tile", "tile broken", "seepage", "water seepage", "roof leak",
                     "plaster", "broken glass", "furniture", "desk broken", "bench broken",
                     "chair broken", "table broken", "railing", "false ceiling"],
    "Mechanical":   ["a.c.", "air condition", "air-condition", "ac not", "ac is not",
                     "ac not working", "cooler", "lift not", "lift is", "elevator",
                     "water pump", "motor", "hvac", "exhaust fan", "chiller", "compressor"],
    "IT / Network": ["wifi", "wi-fi", "internet", "network", " lan ", "projector",
                     "computer", "desktop", "monitor", "printer", "server", "hdmi",
                     "smart board", "smartboard", "av system", "microphone", "mic not",
                     "speaker", "sound system", "no signal", "screen not"],
}

SEVERITY_HIGH = ["danger", "dangerous", "unsafe", "fire", "smoke", "shock", "spark",
                 "flood", "flooding", "collapse", "collapsed", "injury", "injured",
                 "exposed wire", "live wire", "burning", "gas leak", "emergency",
                 "completely", "entire", "whole building", "no water at all"]
SEVERITY_LOW = ["minor", "small", "slight", "cosmetic", "sometimes", "occasionally",
                "a bit", "slightly"]

_SPAM_MARKERS = ["asdf", "qwer", "test test", "lorem ipsum", "aaaa", "1234567", "xyz xyz"]


def _keyword_classify(description: str) -> dict:
    t = f" {(description or '').lower()} "
    # Score by total length of matched keywords so a specific multi-word phrase
    # (e.g. "projector") outweighs a short ambiguous one.
    scores = {c: sum(len(k) for k in KEYWORDS[c] if k in t) for c in CATEGORIES}
    best = max(CATEGORIES, key=lambda c: scores[c])
    hits = scores[best]
    category = best if hits else None

    severity = "medium"
    if any(w in t for w in SEVERITY_HIGH):
        severity = "high"
    elif any(w in t for w in SEVERITY_LOW):
        severity = "low"

    alpha = sum(ch.isalpha() for ch in (description or ""))
    spam = alpha < 8 or any(m in t for m in _SPAM_MARKERS)

    summary = (description or "").strip()
    summary = (summary[:157] + "...") if len(summary) > 160 else summary

    return {
        "category": category,
        "severity": severity,
        "ai_summary": summary or "Infrastructure issue reported.",
        "confidence": 55 if hits else 15,
        "spam_flag": spam,
        "source": "keyword",
    }


def classify(description: str, photo_b64=None, photo_mime="image/jpeg") -> dict:
    ai = engine.classify(description, photo_b64=photo_b64, photo_mime=photo_mime)
    if ai:
        return {
            "category": ai["category"],
            "severity": ai["severity"],
            "ai_summary": ai["summary"],
            "confidence": ai["confidence"],
            "spam_flag": ai["spam"],
            "source": "groq",
        }
    return _keyword_classify(description)


# -- priority score (spec §9) ------------------------------------------------
_SEV = {"high": 45, "medium": 25, "low": 10}
_CAT_RISK = {"Electric": 15, "Power": 15, "Civil": 15, "Mechanical": 8,
             "Plumbing": 6, "IT / Network": 3}


def priority_score(g: dict, *, recurring_group: dict | None = None) -> int:
    score = _SEV.get(g.get("severity"), 25)
    score += _CAT_RISK.get(g.get("category"), 0)

    if recurring_group and recurring_group.get("status") == "active":
        score += min(20, 2 * int(recurring_group.get("report_count", 0)))

    if g.get("status") in ("reported", "verified") and g.get("created_at"):
        days = (time.time() - g["created_at"]) / 86400
        score += min(15, int(days))

    lt = g.get("location_type")
    if lt == "academics_block":
        score += 8
    elif lt == "mess_canteen":
        score += 6
    elif lt == "hostels":
        score += 4
    if g.get("sub_zone") == "Security":
        score += 8
    if g.get("affects_academics"):
        score += 10

    return max(0, min(100, score))
