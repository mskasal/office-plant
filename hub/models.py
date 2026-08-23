"""SQLite schema exactly as specified in spec Section 6."""

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
"""


def connect(db_path: str = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn
