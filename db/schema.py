"""PostgreSQL DDL. Idempotent. Memory mode does not use this."""

DDL = """
CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    display_name  TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('reporter','admin')),
    pin_hash      TEXT NOT NULL,
    department    TEXT,
    contact       TEXT,
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    DOUBLE PRECISION,
    created_by    TEXT
);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

CREATE TABLE IF NOT EXISTS locations (
    id            BIGSERIAL PRIMARY KEY,
    parent_id     BIGINT REFERENCES locations(id) ON DELETE CASCADE,
    location_type TEXT NOT NULL,
    name          TEXT NOT NULL,
    full_path     TEXT UNIQUE NOT NULL,
    is_active     BOOLEAN DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS idx_locations_type ON locations(location_type);

CREATE TABLE IF NOT EXISTS recurring_groups (
    id                   BIGSERIAL PRIMARY KEY,
    location_label       TEXT NOT NULL,
    category             TEXT NOT NULL,
    title                TEXT,
    report_count         INTEGER DEFAULT 0,
    reporter_count       INTEGER DEFAULT 0,
    first_reported_at    DOUBLE PRECISION,
    last_reported_at     DOUBLE PRECISION,
    status               TEXT DEFAULT 'active' CHECK (status IN ('active','resolved')),
    primary_grievance_id BIGINT
);
CREATE INDEX IF NOT EXISTS idx_recurring_key ON recurring_groups(location_label, category);

CREATE TABLE IF NOT EXISTS grievances (
    id                 BIGSERIAL PRIMARY KEY,
    code               TEXT UNIQUE NOT NULL,
    reporter_id        BIGINT REFERENCES users(id),
    reporter_name      TEXT,
    title              TEXT,
    description        TEXT NOT NULL,
    category           TEXT,
    category_confirmed BOOLEAN DEFAULT FALSE,
    severity           TEXT,
    priority_score     INTEGER DEFAULT 0,
    status             TEXT NOT NULL DEFAULT 'reported'
                       CHECK (status IN ('reported','verified','assigned','in_progress',
                                         'resolved','admin_verified','closed')),
    location_type      TEXT,
    block_no           TEXT,
    floor              TEXT,
    room               TEXT,
    sub_zone           TEXT,
    location_label     TEXT,
    responsible_unit   TEXT,
    assignee           TEXT,
    assigned_at        DOUBLE PRECISION,
    due_at             DOUBLE PRECISION,
    recurring_group_id BIGINT REFERENCES recurring_groups(id),
    ai_summary         TEXT,
    ai_confidence      INTEGER,
    spam_flag          BOOLEAN DEFAULT FALSE,
    noticed_at         DOUBLE PRECISION,
    affects_academics  BOOLEAN DEFAULT FALSE,
    primary_photo_url  TEXT,
    thumbnail_url      TEXT,
    created_at         DOUBLE PRECISION,
    updated_at         DOUBLE PRECISION,
    resolved_at        DOUBLE PRECISION,
    closed_at          DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_grievances_status    ON grievances(status);
CREATE INDEX IF NOT EXISTS idx_grievances_category  ON grievances(category);
CREATE INDEX IF NOT EXISTS idx_grievances_created   ON grievances(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_grievances_recurring ON grievances(recurring_group_id);

CREATE TABLE IF NOT EXISTS evidence (
    id            BIGSERIAL PRIMARY KEY,
    grievance_id  BIGINT NOT NULL REFERENCES grievances(id) ON DELETE CASCADE,
    kind          TEXT NOT NULL CHECK (kind IN ('report','resolution_before','resolution_after')),
    image_url     TEXT,
    image_key     TEXT,
    thumbnail_url TEXT,
    note          TEXT,
    uploaded_by   TEXT,
    uploaded_at   DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_evidence_grievance ON evidence(grievance_id);

CREATE TABLE IF NOT EXISTS timeline_events (
    id            BIGSERIAL PRIMARY KEY,
    grievance_id  BIGINT NOT NULL REFERENCES grievances(id) ON DELETE CASCADE,
    event_type    TEXT NOT NULL,
    from_value    TEXT,
    to_value      TEXT,
    actor         TEXT,
    actor_role    TEXT,
    note          TEXT,
    created_at    DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_timeline_grievance ON timeline_events(grievance_id);

CREATE TABLE IF NOT EXISTS notices (
    id           BIGSERIAL PRIMARY KEY,
    title        TEXT NOT NULL,
    body         TEXT,
    audience     TEXT DEFAULT 'all',
    created_by   TEXT,
    created_at   DOUBLE PRECISION,
    is_published BOOLEAN DEFAULT FALSE,
    expires_at   DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    actor       TEXT,
    action      TEXT,
    target_type TEXT,
    target_id   TEXT,
    detail      JSONB,
    created_at  DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at DESC);
"""


def ensure(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(DDL)
    conn.commit()
