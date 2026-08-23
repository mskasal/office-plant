"""Hub-governed per-node config (spec Section 4.1): "the hub is in charge
of schedule/config, but only ever speaks during a window a node itself
opened." This is what M5's validation checklist item 4 needs to actually
be runnable ("push a config change from the hub... confirm a node picks
it up on its next check-in") -- nothing through M4 implemented it despite
the spec committing to it in Section 4.1.

Desired config is operator-set (e.g. via the dashboard) and stored in
`node_config` (hub/models.py). It is never pushed out of band -- only
attached to the CONFIG frame sent back within the same check-in window a
node's own DATA frame opened, per the spec's "only ever speaks during a
window a node itself opened" rule.
"""

import sqlite3
from typing import Callable, Optional

from hub.protocol_frame import ConfigFrame, DataFrame, encode_config_frame


def set_desired_config(
    conn: sqlite3.Connection, node_id: int, wake_interval_sec: int, moisture_dry_threshold_raw: int
) -> None:
    """Records what a node should be running. Takes effect on that node's
    next check-in."""
    conn.execute(
        """
        INSERT INTO node_config (node_id, wake_interval_sec, moisture_dry_threshold_raw)
        VALUES (?, ?, ?)
        ON CONFLICT(node_id) DO UPDATE SET
            wake_interval_sec = excluded.wake_interval_sec,
            moisture_dry_threshold_raw = excluded.moisture_dry_threshold_raw
        """,
        (node_id, wake_interval_sec, moisture_dry_threshold_raw),
    )
    conn.commit()


def get_desired_config(conn: sqlite3.Connection, node_id: int) -> Optional[tuple[int, int]]:
    """Returns (wake_interval_sec, moisture_dry_threshold_raw), or None if
    no operator override has been set for this node."""
    return conn.execute(
        "SELECT wake_interval_sec, moisture_dry_threshold_raw FROM node_config WHERE node_id = ?",
        (node_id,),
    ).fetchone()


def maybe_push_config(conn: sqlite3.Connection, frame: DataFrame, send: Callable[[bytes], None]) -> bool:
    """Called right after ingesting a DATA frame. If an operator has set a
    desired config for `frame.sender_id`, sends it back as a CONFIG frame
    within this same check-in window. Returns True if one was sent."""
    desired = get_desired_config(conn, frame.sender_id)
    if desired is None:
        return False
    wake_interval_sec, moisture_dry_threshold_raw = desired
    send(
        encode_config_frame(
            ConfigFrame(
                target_node_id=frame.sender_id,
                wake_interval_sec=wake_interval_sec,
                moisture_dry_threshold_raw=moisture_dry_threshold_raw,
            )
        )
    )
    return True
