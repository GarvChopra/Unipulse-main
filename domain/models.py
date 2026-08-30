"""Canonical dataclasses + label helpers. Stdlib-only."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class User:
    id: int
    username: str
    display_name: str
    role: str
    department: Optional[str]
    contact: Optional[str]
    is_active: bool
    created_at: float
    created_by: Optional[str]
    pin_hash: Optional[str] = None


@dataclass
class Location:
    id: int
    parent_id: Optional[int]
    location_type: str
    name: str
    full_path: str
    is_active: bool = True


@dataclass
class Grievance:
    id: int
    code: str
    reporter_id: Optional[int]
    reporter_name: str
    title: str
    description: str
    category: Optional[str]
    category_confirmed: bool
    severity: Optional[str]
    priority_score: int
    status: str
    location_type: str
    block_no: Optional[str]
    floor: Optional[str]
    room: Optional[str]
    sub_zone: Optional[str]
    location_label: str
    responsible_unit: Optional[str]
    assignee: Optional[str]
    assigned_at: Optional[float]
    due_at: Optional[float]
    recurring_group_id: Optional[int]
    ai_summary: Optional[str]
    ai_confidence: Optional[int]
    primary_photo_url: Optional[str]
    thumbnail_url: Optional[str]
    created_at: float
    updated_at: float
    resolved_at: Optional[float] = None
    closed_at: Optional[float] = None


@dataclass
class Evidence:
    id: int
    grievance_id: int
    kind: str
    image_url: Optional[str]
    image_key: Optional[str]
    thumbnail_url: Optional[str]
    note: Optional[str]
    uploaded_by: str
    uploaded_at: float


@dataclass
class TimelineEvent:
    id: int
    grievance_id: int
    event_type: str
    from_value: Optional[str]
    to_value: Optional[str]
    actor: str
    actor_role: Optional[str]
    note: Optional[str]
    created_at: float


@dataclass
class RecurringGroup:
    id: int
    location_label: str
    category: str
    title: str
    report_count: int
    reporter_count: int
    first_reported_at: float
    last_reported_at: float
    status: str
    primary_grievance_id: Optional[int]


@dataclass
class Notice:
    id: int
    title: str
    body: str
    audience: str
    created_by: str
    created_at: float
    is_published: bool
    expires_at: Optional[float] = None


def build_location_label(location_type, block_no, floor, room, sub_zone, *, type_names):
    base = type_names.get(location_type, location_type)
    if location_type == "academics_block":
        parts = [base]
        if block_no:
            parts.append(block_no)
        if floor:
            parts.append(floor)
        if room:
            parts.append(f"Room {room}")
        return " > ".join(parts)
    if location_type == "outer_area" and sub_zone:
        return f"{base} > {sub_zone}"
    return base


def recurring_key(location_label: str, category: str) -> str:
    return f"{(location_label or '').strip().lower()}|{(category or '').strip().lower()}"
