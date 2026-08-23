"""SQLite schema. `nodes`/`readings` are exactly as specified in spec
Section 6 -- unmodified since M3. `node_config` is new (M5): spec Section
4.1 commits to hub-governed config push as core v1 behavior, but Section
6's data model never says where the hub stores what it intends to push --
a real gap between those two sections. Kept as its own table rather than
extending `nodes`, since Section 6 fixes that schema exactly."""

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id INTEGER PRIMARY KEY,
    name TEXT,
    role TEXT NOT NULL,
    claimed_at INTEGER,
    last_seen_at INTEGER,
    battery_level INTEGER
);

CREATE TABLE IF NOT EXISTS readings (
    node_id INTEGER NOT NULL,
    timestamp INTEGER NOT NULL,
    moisture_status TEXT NOT NULL,
    FOREIGN KEY (node_id) REFERENCES nodes(id)
);

CREATE TABLE IF NOT EXISTS node_config (
    node_id INTEGER PRIMARY KEY,
    wake_interval_sec INTEGER NOT NULL,
    moisture_dry_threshold_raw INTEGER NOT NULL,
    FOREIGN KEY (node_id) REFERENCES nodes(id)
);
"""


def connect(db_path: str = ":memory:") -> sqlite3.Connection:
    # check_same_thread=False: FastAPI (via Starlette's thread pool for sync
    # routes, and any real ASGI server) may call a route from a different
    # thread than the one that opened this connection. Traffic here is low
    # (tens of nodes, 1-2 wake windows/day per spec Section 4.1) so a single
    # shared connection without extra locking matches the spec's
    # "start simple" ethos rather than a bench-scoped app needing a
    # connection pool.
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn
