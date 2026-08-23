"""Hub-side provisioning (M4 plan, Task 5): discover unclaimed nodes,
claim them (assign a short_address + name, send CLAIM), and hub-side
bookkeeping for factory reset.

Real analog of sim/provisioning.py's Hub class from M0 — same method
names/shapes, now backed by the real `nodes` SQLite table and issuing real
BLINK/CLAIM frames instead of mutating in-memory sim state.

Discovery is necessarily different from the sim, though: a real unclaimed
node has no row anywhere until it's claimed, so "who's nearby and
unclaimed" has to come from something a node actually transmits. That's
the ANNOUNCE frame added in this milestone (see protocol_frame.py) — a gap
in the M4 plan's stated design, where BLINK/CLAIM are hub-initiated and
require already knowing which node to target.
"""

import sqlite3
import time
from dataclasses import dataclass
from typing import Callable, Optional

from hub.protocol_frame import AnnounceFrame, BlinkFrame, ClaimFrame, encode_blink_frame, encode_claim_frame

HUB_ID = 0  # matches sim/node.py's HUB_ID convention

# dBm; needs recalibrating against real RSSI readings once M2's range test
# has run — M0's simulated -8.0 threshold (sim/provisioning.py) was a
# unitless simulation value, never meant to be the production constant.
RSSI_DISCOVERY_THRESHOLD = -60

# An unclaimed node announces roughly every 2s (see
# firmware/main/pairing_mode.c's PAIRING_CYCLE_INTERVAL_MS); tolerate a
# handful of missed cycles from ordinary half-duplex radio contention
# before dropping it off the discover list.
ANNOUNCE_STALE_AFTER_SEC = 10


@dataclass
class _Sighting:
    rssi: int
    last_seen: float


class Hub:
    def __init__(self):
        self._sightings: dict[int, _Sighting] = {}

    def observe_announce(self, frame: AnnounceFrame, rssi: int, now: Optional[float] = None) -> None:
        """Called for every decoded ANNOUNCE frame (see hub/main.py's
        on_frame wiring); records/refreshes that factory_id's sighting."""
        self._sightings[frame.factory_id] = _Sighting(
            rssi=rssi, last_seen=now if now is not None else time.time()
        )

    def discoverable_nodes(
        self,
        conn: sqlite3.Connection,
        threshold: float = RSSI_DISCOVERY_THRESHOLD,
        now: Optional[float] = None,
    ) -> list[int]:
        """Factory IDs currently discoverable: announced recently, at or
        above the RSSI threshold, and not already claimed."""
        now = now if now is not None else time.time()
        claimed_factory_ids = {
            row[0] for row in conn.execute("SELECT id FROM nodes WHERE claimed_at IS NOT NULL").fetchall()
        }
        return [
            factory_id
            for factory_id, sighting in self._sightings.items()
            if factory_id not in claimed_factory_ids
            and sighting.rssi >= threshold
            and (now - sighting.last_seen) <= ANNOUNCE_STALE_AFTER_SEC
        ]

    def blink(self, factory_id: int, send: Callable[[bytes], None]) -> None:
        """Sends BLINK targeting factory_id — the discover page's tap
        action, for the user to visually confirm the physical node."""
        send(encode_blink_frame(BlinkFrame(hub_id=HUB_ID, target_node_id=factory_id)))

    def claim(self, conn: sqlite3.Connection, factory_id: int, name: str, send: Callable[[bytes], None]) -> int:
        """Assigns the next short_address, records the node as claimed, and
        sends CLAIM. Returns the assigned short_address."""
        next_id = (conn.execute("SELECT MAX(id) FROM nodes").fetchone()[0] or HUB_ID) + 1

        conn.execute(
            "INSERT INTO nodes (id, name, role, claimed_at) VALUES (?, ?, 'leaf', ?)",
            (next_id, name, int(time.time())),
        )
        conn.commit()

        self._sightings.pop(factory_id, None)
        send(encode_claim_frame(ClaimFrame(assigned_short_address=next_id, hub_id=HUB_ID)))
        return next_id

    def factory_reset(self, conn: sqlite3.Connection, node_id: int) -> None:
        """Clears this node's hub-side claim record (name, claimed_at).

        Does NOT — and, over this one-way ANNOUNCE/BLINK/CLAIM protocol,
        cannot — force the physical node itself to reset. That's the
        node's own factory-reset button (spec Section 5; M4 plan's
        "Factory reset — hardware button": a 5s hold on the node clears its
        own NVS claim state and reboots into pairing mode). This method is
        the hub-side half of that: once the physical reset happens and the
        node starts announcing again under its original factory_id, this
        clears the stale claim record here so it can be discovered and
        claimed again.
        """
        conn.execute("UPDATE nodes SET name = NULL, claimed_at = NULL WHERE id = ?", (node_id,))
        conn.commit()
