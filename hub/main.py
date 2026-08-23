"""Entry point that wires the real dongle serial port to ingestion and runs
the dashboard server — the actual "hub/" process M3 Task 5's bench test
runs on a Pi (or dev machine, per the M3 plan's own allowance).

Usage:
    python -m hub.main --serial-port /dev/ttyUSB0 --db hub.db
"""

import argparse
import threading
import time

from typing import Callable

from hub.api import create_app
from hub.ingest import ingest_data_frame
from hub.node_config import maybe_push_config
from hub.protocol_frame import AnnounceFrame, DataFrame
from hub.provisioning import Hub as ProvisioningHub
from hub.serial_bridge import ReceivedFrame, SerialBridge, encode_tx_line

# BEACON/JOIN frames are protocol-level only (M2 link-forming concerns) —
# the hub acts on DATA (readings, M3; possible CONFIG push, M5), and
# ANNOUNCE (discovery, M4).
SERIAL_IDLE_POLL_INTERVAL_SEC = 0.05


def make_on_frame(conn, provisioning_hub: ProvisioningHub, send: Callable[[bytes], None]):
    """Builds the SerialBridge callback: DATA frames get ingested as
    readings and may trigger a hub-governed CONFIG push (spec Section
    4.1), ANNOUNCE frames update the provisioning Hub's discoverable-nodes
    registry."""

    def on_frame(received: ReceivedFrame) -> None:
        if isinstance(received.frame, DataFrame):
            ingest_data_frame(conn, received.frame, timestamp=int(time.time()))
            maybe_push_config(conn, received.frame, send)
        elif isinstance(received.frame, AnnounceFrame):
            provisioning_hub.observe_announce(received.frame, rssi=received.rssi)

    return on_frame


def serial_poll_loop(bridge: SerialBridge, stop_event: threading.Event) -> None:
    """Runs bridge.poll_once() until stop_event is set, backing off briefly
    when the dongle has nothing queued so this doesn't busy-spin a core."""
    while not stop_event.is_set():
        if not bridge.poll_once():
            time.sleep(SERIAL_IDLE_POLL_INTERVAL_SEC)


def main() -> None:
    # Imported here, not at module scope, so importing hub.main for its
    # testable pieces (make_on_frame, serial_poll_loop) doesn't require
    # pyserial/uvicorn to be installed.
    import serial
    import uvicorn

    parser = argparse.ArgumentParser(description="Office Plant Swarm hub")
    parser.add_argument("--serial-port", required=True, help="Dongle's serial device, e.g. /dev/ttyUSB0")
    parser.add_argument("--baud-rate", type=int, default=115200, help="Must match dongle_uart.c's DONGLE_UART_BAUD_RATE")
    parser.add_argument("--db", default="hub.db")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--http-port", type=int, default=8000)
    args = parser.parse_args()

    app = create_app(db_path=args.db)

    port = serial.Serial(args.serial_port, args.baud_rate, timeout=1)

    def send(payload: bytes) -> None:
        port.write(encode_tx_line(payload).encode("ascii"))

    app.state.send = send  # replaces create_app's no-op default now that a real port exists
    bridge = SerialBridge(port, on_frame=make_on_frame(app.state.conn, app.state.provisioning_hub, send))

    stop_event = threading.Event()
    poll_thread = threading.Thread(target=serial_poll_loop, args=(bridge, stop_event), daemon=True)
    poll_thread.start()

    try:
        uvicorn.run(app, host=args.host, port=args.http_port)
    finally:
        stop_event.set()


if __name__ == "__main__":
    main()
