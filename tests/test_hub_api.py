import time

from fastapi.testclient import TestClient

from hub.api import DEFAULT_WAKE_INTERVAL_SEC, OFFLINE_THRESHOLD_MULTIPLIER, create_app


def _client_with_conn():
    app = create_app(db_path=":memory:")
    return TestClient(app), app.state.conn


def test_dashboard_shows_placeholder_when_no_nodes_reported():
    client, _ = _client_with_conn()
    resp = client.get("/")
    assert resp.status_code == 200
    assert "No nodes have reported yet." in resp.text


def test_dashboard_shows_named_node_with_latest_reading():
    client, conn = _client_with_conn()
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
    client, conn = _client_with_conn()
    now = int(time.time())
    conn.execute("INSERT INTO nodes (id, role, last_seen_at, battery_level) VALUES (5, 'leaf', ?, 50)", (now,))
    conn.commit()

    resp = client.get("/")

    assert "node-5" in resp.text


def test_dashboard_marks_stale_node_offline():
    client, conn = _client_with_conn()
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
    client, conn = _client_with_conn()
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
