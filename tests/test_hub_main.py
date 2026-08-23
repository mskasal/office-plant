import threading
import time

from hub.main import make_on_frame, serial_poll_loop
from hub.models import connect
from hub.protocol_frame import AnnounceFrame, BeaconFrame, DataFrame, NeedsWater
from hub.provisioning import Hub as ProvisioningHub
from hub.serial_bridge import ReceivedFrame


def test_make_on_frame_ingests_data_frames():
    conn = connect()
    on_frame = make_on_frame(conn, ProvisioningHub())

    on_frame(ReceivedFrame(frame=DataFrame(sender_id=1, needs_water=NeedsWater.TRUE, battery_pct=80, timestamp=0), rssi=-50))

    node = conn.execute("SELECT id, battery_level FROM nodes WHERE id = 1").fetchone()
    assert node == (1, 80)


def test_make_on_frame_records_announce_frames_in_provisioning_hub():
    conn = connect()
    provisioning_hub = ProvisioningHub()
    on_frame = make_on_frame(conn, provisioning_hub)

    on_frame(ReceivedFrame(frame=AnnounceFrame(factory_id=0xBEEF), rssi=-40))

    assert provisioning_hub.discoverable_nodes(conn) == [0xBEEF]


def test_make_on_frame_ignores_beacon_frames():
    conn = connect()
    on_frame = make_on_frame(conn, ProvisioningHub())

    on_frame(ReceivedFrame(frame=BeaconFrame(sender_id=0, hop_count=0), rssi=-40))

    assert conn.execute("SELECT COUNT(*) FROM nodes").fetchone() == (0,)


class _FakeBridge:
    def __init__(self, poll_results):
        self._results = list(poll_results)
        self.poll_count = 0

    def poll_once(self):
        self.poll_count += 1
        if self._results:
            return self._results.pop(0)
        return False


def test_serial_poll_loop_stops_when_event_is_set():
    bridge = _FakeBridge([True, True, False])
    stop_event = threading.Event()

    def run_briefly():
        serial_poll_loop(bridge, stop_event)

    thread = threading.Thread(target=run_briefly)
    thread.start()
    time.sleep(0.2)
    stop_event.set()
    thread.join(timeout=2)

    assert not thread.is_alive()
    assert bridge.poll_count > 0
