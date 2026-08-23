from sim.node import Node, HUB_ID


def test_node_defaults():
    n = Node(node_id=1, position=(0.0, 0.0), role="leaf")
    assert n.battery_pct == 100.0
    assert n.needs_water is None
    assert n.hop_count is None
    assert n.parent_id is None
    assert n.claimed is False


def test_hub_id_is_zero():
    assert HUB_ID == 0
