from sim.node import Node, HUB_ID
from sim.network import Network
from sim.protocol import run_wake_window, collect_data


def test_collect_data_includes_only_attached_nodes():
    net = Network(radio_range=10.0)
    net.add_node(Node(node_id=HUB_ID, position=(0.0, 0.0), role="hub"))
    net.add_node(Node(node_id=1, position=(5.0, 0.0), role="leaf", needs_water=True, battery_pct=80.0))
    net.add_node(Node(node_id=2, position=(100.0, 0.0), role="leaf", needs_water=False))  # isolated

    run_wake_window(net)
    frames = collect_data(net, timestamp=42)

    assert set(frames.keys()) == {1}
    frame = frames[1]
    assert frame.source_id == 1
    assert frame.needs_water is True
    assert frame.battery_pct == 80.0
    assert frame.timestamp == 42
