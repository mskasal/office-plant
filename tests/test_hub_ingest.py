from hub.ingest import ingest_data_frame
from hub.models import connect
from hub.protocol_frame import DataFrame, NeedsWater


def test_ingest_inserts_node_and_reading_for_new_node():
    conn = connect()
    frame = DataFrame(sender_id=1, needs_water=NeedsWater.TRUE, battery_pct=80, timestamp=0)

    ingest_data_frame(conn, frame, timestamp=100)

    node = conn.execute("SELECT id, role, last_seen_at, battery_level FROM nodes WHERE id = 1").fetchone()
    assert node == (1, "leaf", 100, 80)

    reading = conn.execute(
        "SELECT node_id, timestamp, moisture_status FROM readings WHERE node_id = 1"
    ).fetchone()
    assert reading == (1, 100, "TRUE")


def test_ingest_upserts_existing_node_without_clobbering_name():
    conn = connect()
    conn.execute("INSERT INTO nodes (id, name, role, last_seen_at, battery_level) VALUES (1, 'Ficus', 'leaf', 0, 100)")
    conn.commit()

    frame = DataFrame(sender_id=1, needs_water=NeedsWater.FALSE, battery_pct=90, timestamp=0)
    ingest_data_frame(conn, frame, timestamp=200)

    node = conn.execute("SELECT id, name, last_seen_at, battery_level FROM nodes WHERE id = 1").fetchone()
    assert node == (1, "Ficus", 200, 90)


def test_ingest_appends_multiple_readings_over_time():
    conn = connect()
    frame1 = DataFrame(sender_id=1, needs_water=NeedsWater.TRUE, battery_pct=80, timestamp=0)
    frame2 = DataFrame(sender_id=1, needs_water=NeedsWater.FALSE, battery_pct=79, timestamp=0)

    ingest_data_frame(conn, frame1, timestamp=100)
    ingest_data_frame(conn, frame2, timestamp=200)

    readings = conn.execute(
        "SELECT timestamp, moisture_status FROM readings WHERE node_id = 1 ORDER BY timestamp"
    ).fetchall()
    assert readings == [(100, "TRUE"), (200, "FALSE")]

    node = conn.execute("SELECT last_seen_at, battery_level FROM nodes WHERE id = 1").fetchone()
    assert node == (200, 79)
