from hub.models import connect


def test_connect_is_idempotent_against_the_same_file(tmp_path):
    # CREATE TABLE IF NOT EXISTS must not error on a second connect() against
    # the same on-disk file (the hub process restarting against existing data).
    db_path = str(tmp_path / "hub.db")
    conn1 = connect(db_path)
    conn1.execute("INSERT INTO nodes (id, role) VALUES (1, 'leaf')")
    conn1.commit()
    conn1.close()

    conn2 = connect(db_path)
    row = conn2.execute("SELECT id, role FROM nodes WHERE id = 1").fetchone()
    assert row == (1, "leaf")


def test_connect_creates_nodes_and_readings_tables():
    conn = connect()
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert {"nodes", "readings", "node_config"} <= tables


def test_nodes_table_has_spec_section_6_columns():
    conn = connect()
    columns = {row[1] for row in conn.execute("PRAGMA table_info(nodes)").fetchall()}
    assert columns == {"id", "name", "role", "claimed_at", "last_seen_at", "battery_level"}


def test_readings_table_has_spec_section_6_columns():
    conn = connect()
    columns = {row[1] for row in conn.execute("PRAGMA table_info(readings)").fetchall()}
    assert columns == {"node_id", "timestamp", "moisture_status"}
