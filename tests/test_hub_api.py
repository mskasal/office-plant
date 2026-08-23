import time

from fastapi.testclient import TestClient

from hub.api import DEFAULT_WAKE_INTERVAL_SEC, OFFLINE_THRESHOLD_MULTIPLIER, create_app
from hub.protocol_frame import AnnounceFrame, decode_claim_frame


def _client_with_conn(send=None):
    app = create_app(db_path=":memory:", send=send)
    return TestClient(app), app.state.conn, app.state.provisioning_hub


def test_dashboard_shows_placeholder_when_no_nodes_reported():
    client, _, _ = _client_with_conn()
    resp = client.get("/")
    assert resp.status_code == 200
    assert "No nodes have reported yet." in resp.text


def test_dashboard_shows_named_node_with_latest_reading():
    client, conn, _ = _client_with_conn()
    now = int(time.time())
    conn.execute(
        "INSERT INTO nodes (id, name, role, last_seen_at, battery_level) VALUES (1, 'Ficus', 'leaf', ?, 87)",
        (now,),
    )
    conn.execute("INSERT INTO readings (node_id, timestamp, moisture_status) VALUES (1, ?, 'TRUE')", (now,))
    conn.commit()

    resp = client.get("/")

    assert "Ficus" in resp.text
    assert "Needs water" in resp.text
    assert "87%" in resp.text


def test_dashboard_falls_back_to_placeholder_name_for_unclaimed_node():
    client, conn, _ = _client_with_conn()
    now = int(time.time())
    conn.execute("INSERT INTO nodes (id, role, last_seen_at, battery_level) VALUES (5, 'leaf', ?, 50)", (now,))
    conn.commit()

    resp = client.get("/")

    assert "node-5" in resp.text


def test_dashboard_marks_stale_node_offline():
    client, conn, _ = _client_with_conn()
    stale_time = int(time.time()) - (DEFAULT_WAKE_INTERVAL_SEC * OFFLINE_THRESHOLD_MULTIPLIER) - 1
    conn.execute(
        "INSERT INTO nodes (id, name, role, last_seen_at, battery_level) VALUES (1, 'Ficus', 'leaf', ?, 20)",
        (stale_time,),
    )
    conn.execute(
        "INSERT INTO readings (node_id, timestamp, moisture_status) VALUES (1, ?, 'FALSE')", (stale_time,)
    )
    conn.commit()

    resp = client.get("/")

    assert "Offline" in resp.text


def test_dashboard_shows_most_recent_reading_when_multiple_exist():
    client, conn, _ = _client_with_conn()
    now = int(time.time())
    conn.execute(
        "INSERT INTO nodes (id, name, role, last_seen_at, battery_level) VALUES (1, 'Ficus', 'leaf', ?, 60)",
        (now,),
    )
    conn.execute("INSERT INTO readings (node_id, timestamp, moisture_status) VALUES (1, ?, 'TRUE')", (now - 100,))
    conn.execute("INSERT INTO readings (node_id, timestamp, moisture_status) VALUES (1, ?, 'FALSE')", (now,))
    conn.commit()

    resp = client.get("/")

    assert "OK" in resp.text
    assert "Needs water" not in resp.text


def test_discover_page_shows_placeholder_when_nothing_announcing():
    client, _, _ = _client_with_conn()
    resp = client.get("/discover")
    assert resp.status_code == 200
    assert "No unclaimed nodes discoverable" in resp.text


def test_discover_page_lists_announcing_factory_id():
    client, _, provisioning_hub = _client_with_conn()
    provisioning_hub.observe_announce(AnnounceFrame(factory_id=0xBEEF), rssi=-40)

    resp = client.get("/discover")

    assert "beef" in resp.text.lower()


def test_discover_blink_calls_send_with_blink_frame():
    sent = []
    client, _, provisioning_hub = _client_with_conn(send=sent.append)
    provisioning_hub.observe_announce(AnnounceFrame(factory_id=0xBEEF), rssi=-40)

    resp = client.post("/discover/48879/blink", follow_redirects=False)  # 0xBEEF = 48879

    assert resp.status_code == 303
    assert len(sent) == 1


def test_discover_claim_creates_node_and_removes_it_from_discover_page():
    sent = []
    client, conn, provisioning_hub = _client_with_conn(send=sent.append)
    provisioning_hub.observe_announce(AnnounceFrame(factory_id=0xBEEF), rssi=-40)

    resp = client.post("/discover/48879/claim", data={"name": "Ficus"}, follow_redirects=False)

    assert resp.status_code == 303
    assert len(sent) == 1
    claim = decode_claim_frame(sent[0])
    assert claim is not None
    assert claim.assigned_short_address == 1

    node = conn.execute("SELECT name FROM nodes WHERE id = 1").fetchone()
    assert node == ("Ficus",)

    discover_resp = client.get("/discover")
    assert "No unclaimed nodes discoverable" in discover_resp.text


def test_set_node_config_stores_desired_config_and_redirects():
    client, conn, _ = _client_with_conn()
    conn.execute("INSERT INTO nodes (id, role) VALUES (1, 'leaf')")
    conn.commit()

    resp = client.post(
        "/nodes/1/config",
        data={"wake_interval_sec": "3600", "moisture_dry_threshold_raw": "1900"},
        follow_redirects=False,
    )

    assert resp.status_code == 303
    row = conn.execute(
        "SELECT wake_interval_sec, moisture_dry_threshold_raw FROM node_config WHERE node_id = 1"
    ).fetchone()
    assert row == (3600, 1900)


def test_dashboard_uses_configured_wake_interval_for_offline_threshold():
    client, conn, _ = _client_with_conn()
    # Configured interval is 1 hour; last seen 90 minutes ago -- offline
    # under the real configured interval, but would read as "online" if the
    # dashboard incorrectly fell back to the 30s bench default.
    configured_interval_sec = 3600
    last_seen = int(time.time()) - (configured_interval_sec * OFFLINE_THRESHOLD_MULTIPLIER) - 1
    conn.execute(
        "INSERT INTO nodes (id, name, role, last_seen_at, battery_level) VALUES (1, 'Ficus', 'leaf', ?, 50)",
        (last_seen,),
    )
    conn.execute(
        "INSERT INTO node_config (node_id, wake_interval_sec, moisture_dry_threshold_raw) VALUES (1, ?, 2000)",
        (configured_interval_sec,),
    )
    conn.commit()

    resp = client.get("/")

    assert "Offline" in resp.text
