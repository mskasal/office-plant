"""On a decoded DATA frame, upsert the node's freshness/battery and append
a reading row."""

import sqlite3

from hub.protocol_frame import DataFrame


def ingest_data_frame(conn: sqlite3.Connection, frame: DataFrame, timestamp: int) -> None:
    """Upserts nodes.last_seen_at/battery_level and inserts a readings row.

    A node not yet claimed/named (provisioning is M4's job, spec Section 5)
    still gets a row here with name=NULL — the dashboard (M3 Task 4) falls
    back to a placeholder label for those.
    """
    conn.execute(
        """
        INSERT INTO nodes (id, role, last_seen_at, battery_level)
        VALUES (?, 'leaf', ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            last_seen_at = excluded.last_seen_at,
            battery_level = excluded.battery_level
        """,
        (frame.sender_id, timestamp, frame.battery_pct),
    )
    conn.execute(
        "INSERT INTO readings (node_id, timestamp, moisture_status) VALUES (?, ?, ?)",
        (frame.sender_id, timestamp, frame.needs_water.name),
    )
    conn.commit()
