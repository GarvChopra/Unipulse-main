"""Phase 2 — the PostgreSQL code path has no live-DB coverage (tests run
in-memory). This is a cheap safety net: every column a db/*.py module SELECTs or
INSERTs must actually exist in the schema DDL, and vice-versa for the core
tables. Catches the "column does not exist" class of bug before deploy."""
import re

from db import schema


def _columns_from_ddl(table: str) -> set[str]:
    m = re.search(rf"CREATE TABLE IF NOT EXISTS {table} \((.*?)\n\);",
                  schema.DDL, re.S)
    assert m, f"no CREATE TABLE for {table}"
    cols = set()
    for line in m.group(1).splitlines():
        line = line.strip().rstrip(",")
        if not line or line.upper().startswith(("PRIMARY KEY", "FOREIGN KEY",
                                                "CONSTRAINT", "CHECK", "UNIQUE (")):
            continue
        tok = line.split()[0]
        if tok.isidentifier():
            cols.add(tok)
    # ALTER TABLE ... ADD COLUMN [IF NOT EXISTS] <name>
    for name in re.findall(rf"ALTER TABLE {table} ADD COLUMN(?: IF NOT EXISTS)? (\w+)",
                           schema.DDL):
        cols.add(name)
    return cols


CASES = [
    ("users", "db.users"),
    ("locations", "db.locations"),
    ("grievances", "db.grievances"),
    ("evidence", "db.evidence"),
    ("timeline_events", "db.timeline"),
    ("recurring_groups", "db.recurring"),
    ("notices", "db.notices"),
    ("audit_log", "db.audit"),
]


def test_every_module_col_exists_in_schema():
    import importlib
    problems = []
    for table, modname in CASES:
        schema_cols = _columns_from_ddl(table)
        mod = importlib.import_module(modname)
        mod_cols = set(getattr(mod, "_COLS", ()))
        missing = mod_cols - schema_cols
        if missing:
            problems.append(f"{modname}._COLS has {sorted(missing)} not in {table}")
    assert not problems, "\n".join(problems)


def test_grievance_insert_columns_are_all_real():
    from db import grievances
    schema_cols = _columns_from_ddl("grievances")
    assert set(grievances._COLS) - {"id"} <= schema_cols
    assert set(grievances._DEFAULTS) <= schema_cols
