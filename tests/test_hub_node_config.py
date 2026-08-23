from hub.models import connect
from hub.node_config import get_desired_config, maybe_push_config, set_desired_config
from hub.protocol_frame import ConfigFrame, DataFrame, NeedsWater, decode_config_frame


class _FakeSender:
    def __init__(self):
        self.sent: list[bytes] = []

    def __call__(self, payload: bytes) -> None:
        self.sent.append(payload)


def test_get_desired_config_returns_none_when_unset():
    conn = connect()
    assert get_desired_config(conn, node_id=1) is None


def test_set_desired_config_then_get_round_trips():
    conn = connect()
    conn.execute("INSERT INTO nodes (id, role) VALUES (1, 'leaf')")
    conn.commit()

    set_desired_config(conn, node_id=1, wake_interval_sec=3600, moisture_dry_threshold_raw=1900)

    assert get_desired_config(conn, node_id=1) == (3600, 1900)


def test_set_desired_config_upserts_on_repeat_calls():
    conn = connect()
    conn.execute("INSERT INTO nodes (id, role) VALUES (1, 'leaf')")
    conn.commit()

    set_desired_config(conn, node_id=1, wake_interval_sec=3600, moisture_dry_threshold_raw=1900)
    set_desired_config(conn, node_id=1, wake_interval_sec=7200, moisture_dry_threshold_raw=2100)

    assert get_desired_config(conn, node_id=1) == (7200, 2100)
    assert conn.execute("SELECT COUNT(*) FROM node_config").fetchone() == (1,)


def test_maybe_push_config_does_nothing_when_no_override_set():
    conn = connect()
    send = _FakeSender()
    frame = DataFrame(sender_id=1, needs_water=NeedsWater.TRUE, battery_pct=80, timestamp=0)

    sent = maybe_push_config(conn, frame, send)

    assert sent is False
    assert send.sent == []


def test_maybe_push_config_sends_config_frame_when_override_set():
    conn = connect()
    conn.execute("INSERT INTO nodes (id, role) VALUES (1, 'leaf')")
    conn.commit()
    set_desired_config(conn, node_id=1, wake_interval_sec=3600, moisture_dry_threshold_raw=1900)

    send = _FakeSender()
    frame = DataFrame(sender_id=1, needs_water=NeedsWater.TRUE, battery_pct=80, timestamp=0)

    sent = maybe_push_config(conn, frame, send)

    assert sent is True
    assert len(send.sent) == 1
    config = decode_config_frame(send.sent[0])
    assert config == ConfigFrame(target_node_id=1, wake_interval_sec=3600, moisture_dry_threshold_raw=1900)


def test_maybe_push_config_targets_only_the_reporting_node():
    conn = connect()
    conn.execute("INSERT INTO nodes (id, role) VALUES (1, 'leaf'), (2, 'leaf')")
    conn.commit()
    set_desired_config(conn, node_id=2, wake_interval_sec=3600, moisture_dry_threshold_raw=1900)

    send = _FakeSender()
    frame = DataFrame(sender_id=1, needs_water=NeedsWater.TRUE, battery_pct=80, timestamp=0)

    sent = maybe_push_config(conn, frame, send)

    assert sent is False
    assert send.sent == []
