"""The hub's local web app (spec Section 6): a single page listing every
node with its last-known moisture status, battery level, and last-seen
time, pull model, refreshed when you open the page.

FastAPI is the spec's tentative default (Section 3), not yet finalized
there; kept as-is here per the M3 plan's Task 4 instruction to re-confirm
rather than silently swap frameworks — nothing since M0 has raised the
"efficiency over dev speed" concern the spec flags as the trigger to
reconsider it.
"""

import time
from pathlib import Path
from typing import Callable, Optional

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from hub.models import connect
from hub.node_config import set_desired_config
from hub.provisioning import Hub as ProvisioningHub

DASHBOARD_DIR = Path(__file__).parent / "dashboard"
templates = Jinja2Templates(directory=str(DASHBOARD_DIR / "templates"))

# Fallback for a node with no operator-set config yet (hub/node_config.py,
# M5) — matches M1/M2 firmware's hardcoded TEST_WAKE_INTERVAL_SEC=30.
DEFAULT_WAKE_INTERVAL_SEC = 30
OFFLINE_THRESHOLD_MULTIPLIER = 2  # spec Section 6: ">2x its expected interval"


def create_app(db_path: str = "hub.db", send: Optional[Callable[[bytes], None]] = None) -> FastAPI:
    """`send` transmits an encoded frame to the dongle (real usage: bound to
    a live SerialBridge.send, wired in hub/main.py). Defaults to a no-op so
    the dashboard still runs standalone for bench testing without hardware
    attached (per docs/developer-setup.md's dev-machine allowance) — BLINK/
    CLAIM requests just silently go nowhere in that mode."""
    app = FastAPI()
    app.state.conn = connect(db_path)
    app.state.provisioning_hub = ProvisioningHub()
    app.state.send = send or (lambda payload: None)

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        now = int(time.time())
        rows = app.state.conn.execute(
            """
            SELECT n.id, n.name, n.battery_level, n.last_seen_at, r.moisture_status, c.wake_interval_sec
            FROM nodes n
            LEFT JOIN readings r
                ON r.node_id = n.id
                AND r.timestamp = (SELECT MAX(timestamp) FROM readings WHERE node_id = n.id)
            LEFT JOIN node_config c ON c.node_id = n.id
            ORDER BY n.id
            """
        ).fetchall()

        nodes = []
        for node_id, name, battery_level, last_seen_at, moisture_status, wake_interval_sec in rows:
            # Each node's own configured interval when an operator has set
            # one (hub/node_config.py, M5); DEFAULT_WAKE_INTERVAL_SEC
            # otherwise, since a node not yet given a real production
            # interval is still running M1/M2 firmware's 30s bench default.
            offline_after_sec = (wake_interval_sec or DEFAULT_WAKE_INTERVAL_SEC) * OFFLINE_THRESHOLD_MULTIPLIER
            is_offline = last_seen_at is None or (now - last_seen_at) > offline_after_sec
            nodes.append(
                {
                    "id": node_id,
                    "name": name or f"node-{node_id}",
                    "battery_level": battery_level,
                    "last_seen_at": last_seen_at,
                    "moisture_status": moisture_status,
                    "offline": is_offline,
                    "wake_interval_sec": wake_interval_sec,
                }
            )

        return templates.TemplateResponse(request, "index.html", {"nodes": nodes})

    @app.post("/nodes/{node_id}/config")
    def set_node_config(node_id: int, wake_interval_sec: int = Form(...), moisture_dry_threshold_raw: int = Form(...)):
        """Sets the desired config for a node (spec Section 4.1); takes
        effect on that node's next check-in, per maybe_push_config in
        hub/node_config.py — never pushed out of band."""
        set_desired_config(app.state.conn, node_id, wake_interval_sec, moisture_dry_threshold_raw)
        return RedirectResponse("/", status_code=303)

    @app.get("/discover", response_class=HTMLResponse)
    def discover(request: Request):
        factory_ids = app.state.provisioning_hub.discoverable_nodes(app.state.conn)
        return templates.TemplateResponse(request, "discover.html", {"factory_ids": factory_ids})

    @app.post("/discover/{factory_id}/blink")
    def discover_blink(factory_id: int):
        app.state.provisioning_hub.blink(factory_id, app.state.send)
        return RedirectResponse("/discover", status_code=303)

    @app.post("/discover/{factory_id}/claim")
    def discover_claim(factory_id: int, name: str = Form(...)):
        app.state.provisioning_hub.claim(app.state.conn, factory_id, name, app.state.send)
        return RedirectResponse("/discover", status_code=303)

    return app
