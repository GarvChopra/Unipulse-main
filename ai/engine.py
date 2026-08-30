"""Groq classification for campus grievances. Optional - degrades to None."""
from __future__ import annotations

import json

import requests

from config import Config
from domain.constants import CATEGORIES, GLB, SEVERITIES

_URL = "https://api.groq.com/openai/v1/chat/completions"
_TIMEOUT = 20

_SYSTEM = (
    f"You triage infrastructure grievances reported by faculty at {GLB['name']}. "
    f"Classify each report into exactly ONE category from this list: {', '.join(CATEGORIES)}. "
    "Estimate severity as low, medium, or high (high = safety risk, total loss of a "
    "critical service, or many people affected). Write a single-sentence plain summary. "
    "Give a confidence 0-100. Set spam=true only if the text is clearly not a real "
    "infrastructure report (gibberish, a test, abuse). "
    'Respond ONLY with JSON: {"category": "...", "severity": "...", '
    '"summary": "...", "confidence": 0, "spam": false}'
)


def is_available() -> bool:
    return bool(Config.GROQ_API_KEY)


def classify(description: str, photo_b64: str | None = None,
             photo_mime: str = "image/jpeg") -> dict | None:
    if not is_available():
        return None

    if photo_b64:
        model = Config.GROQ_MODEL_VISION
        user_content: object = [
            {"type": "text", "text": f"Report text: {description or '(none)'}"},
            {"type": "image_url",
             "image_url": {"url": f"data:{photo_mime};base64,{photo_b64}"}},
        ]
    else:
        model = Config.GROQ_MODEL_TEXT
        user_content = f"Report text: {description}"

    body = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": 400,
        # qwen3 hybrid-reasoning models spend the token budget on reasoning and
        # then fail JSON mode; "none" keeps the response as plain JSON.
        "reasoning_effort": "none",
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user_content},
        ],
    }
    try:
        r = requests.post(_URL, json=body, timeout=_TIMEOUT,
                          headers={"Authorization": f"Bearer {Config.GROQ_API_KEY}"})
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"]
        data = json.loads(raw)
    except Exception as e:  # noqa: BLE001
        print(f"[ai.engine] classify failed: {type(e).__name__}: {e}")
        return None

    category = str(data.get("category", "")).strip()
    if category not in CATEGORIES:
        norm = category.replace(" ", "").lower()
        category = next((c for c in CATEGORIES if c.replace(" ", "").lower() == norm), None)
    if not category:
        return None

    severity = str(data.get("severity", "medium")).strip().lower()
    if severity not in SEVERITIES:
        severity = "medium"
    try:
        confidence = max(0, min(100, int(data.get("confidence", 60))))
    except (TypeError, ValueError):
        confidence = 60

    return {
        "category": category,
        "severity": severity,
        "summary": (str(data.get("summary", "")).strip() or (description or "")[:160]),
        "confidence": confidence,
        "spam": bool(data.get("spam", False)),
    }
