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

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from hub.models import connect

DASHBOARD_DIR = Path(__file__).parent / "dashboard"
templates = Jinja2Templates(directory=str(DASHBOARD_DIR / "templates"))

# M3 has no per-node wake schedule yet (that arrives with M4's hub-governed
# config push, spec Section 4.1) — this bench-only constant matches M1/M2
# firmware's hardcoded TEST_WAKE_INTERVAL_SEC=30 and should be replaced by a
# real per-node interval once M4 exists.
DEFAULT_WAKE_INTERVAL_SEC = 30
OFFLINE_THRESHOLD_MULTIPLIER = 2  # spec Section 6: ">2x its expected interval"


def create_app(db_path: str = "hub.db") -> FastAPI:
    app = FastAPI()
    app.state.conn = connect(db_path)

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        now = int(time.time())
        rows = app.state.conn.execute(
            """
            SELECT n.id, n.name, n.battery_level, n.last_seen_at, r.moisture_status
            FROM nodes n
            LEFT JOIN readings r
                ON r.node_id = n.id
                AND r.timestamp = (SELECT MAX(timestamp) FROM readings WHERE node_id = n.id)
            ORDER BY n.id
            """
        ).fetchall()

        offline_after_sec = DEFAULT_WAKE_INTERVAL_SEC * OFFLINE_THRESHOLD_MULTIPLIER
        nodes = []
        for node_id, name, battery_level, last_seen_at, moisture_status in rows:
            is_offline = last_seen_at is None or (now - last_seen_at) > offline_after_sec
            nodes.append(
                {
                    "id": node_id,
                    "name": name or f"node-{node_id}",
                    "battery_level": battery_level,
                    "last_seen_at": last_seen_at,
                    "moisture_status": moisture_status,
                    "offline": is_offline,
                }
            )

        return templates.TemplateResponse(request, "index.html", {"nodes": nodes})

    return app
