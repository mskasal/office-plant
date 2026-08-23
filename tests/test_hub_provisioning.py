from hub.models import connect
from hub.protocol_frame import AnnounceFrame, BlinkFrame, ClaimFrame, decode_blink_frame, decode_claim_frame
from hub.provisioning import ANNOUNCE_STALE_AFTER_SEC, RSSI_DISCOVERY_THRESHOLD, HUB_ID, Hub


class _FakeSender:
    def __init__(self):
        self.sent: list[bytes] = []

    def __call__(self, payload: bytes) -> None:
        self.sent.append(payload)


def test_only_nearby_recently_announced_nodes_are_discoverable():
    conn = connect()
    hub = Hub()
    hub.observe_announce(AnnounceFrame(factory_id=1), rssi=-40, now=1000.0)  # near
    hub.observe_announce(AnnounceFrame(factory_id=2), rssi=-90, now=1000.0)  # too far

    assert hub.discoverable_nodes(conn, now=1000.0) == [1]


def test_stale_announces_are_not_discoverable():
    conn = connect()
    hub = Hub()
    hub.observe_announce(AnnounceFrame(factory_id=1), rssi=-40, now=1000.0)

    stale_now = 1000.0 + ANNOUNCE_STALE_AFTER_SEC + 1
    assert hub.discoverable_nodes(conn, now=stale_now) == []


def test_claim_removes_node_from_discovery_records_it_and_sends_claim_frame():
    conn = connect()
    hub = Hub()
    hub.observe_announce(AnnounceFrame(factory_id=42), rssi=-40, now=1000.0)
    send = _FakeSender()

    assigned_id = hub.claim(conn, factory_id=42, name="Ficus - meeting room", send=send)

    assert assigned_id == 1  # first claimed node after HUB_ID=0
    row = conn.execute("SELECT id, name, role, claimed_at FROM nodes WHERE id = ?", (assigned_id,)).fetchone()
    assert row[0] == 1
    assert row[1] == "Ficus - meeting room"
    assert row[2] == "leaf"
    assert row[3] is not None

    assert hub.discoverable_nodes(conn, now=1000.0) == []

    assert len(send.sent) == 1
    claim = decode_claim_frame(send.sent[0])
    assert claim == ClaimFrame(assigned_short_address=1, hub_id=HUB_ID)


def test_claim_assigns_increasing_addresses():
    conn = connect()
    hub = Hub()
    send = _FakeSender()

    first_id = hub.claim(conn, factory_id=1, name="Ficus", send=send)
    second_id = hub.claim(conn, factory_id=2, name="Monstera", send=send)

    assert second_id == first_id + 1


def test_blink_sends_blink_frame_targeting_factory_id():
    send = _FakeSender()
    hub = Hub()

    hub.blink(factory_id=0xBEEF, send=send)

    assert len(send.sent) == 1
    blink = decode_blink_frame(send.sent[0])
    assert blink == BlinkFrame(hub_id=HUB_ID, target_node_id=0xBEEF)


def test_factory_reset_clears_claim_record_without_deleting_readings_history():
    conn = connect()
    hub = Hub()
    send = _FakeSender()
    node_id = hub.claim(conn, factory_id=42, name="Ficus", send=send)
    conn.execute("INSERT INTO readings (node_id, timestamp, moisture_status) VALUES (?, 0, 'TRUE')", (node_id,))
    conn.commit()

    hub.factory_reset(conn, node_id)

    row = conn.execute("SELECT name, claimed_at FROM nodes WHERE id = ?", (node_id,)).fetchone()
    assert row == (None, None)
    # Historical readings are untouched -- factory reset clears the claim,
    # not the plant's history.
    assert conn.execute("SELECT COUNT(*) FROM readings WHERE node_id = ?", (node_id,)).fetchone() == (1,)


def test_discovery_threshold_default_matches_module_constant():
    conn = connect()
    hub = Hub()
    hub.observe_announce(AnnounceFrame(factory_id=1), rssi=RSSI_DISCOVERY_THRESHOLD, now=1000.0)
    hub.observe_announce(AnnounceFrame(factory_id=2), rssi=RSSI_DISCOVERY_THRESHOLD - 1, now=1000.0)

    assert hub.discoverable_nodes(conn, now=1000.0) == [1]
