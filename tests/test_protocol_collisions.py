import random

from sim.node import Node, HUB_ID
from sim.network import Network
from sim.protocol import assign_jitter, resolve_join_collisions, run_wake_window


def test_assign_jitter_is_deterministic_for_a_given_seed():
    jitter_a = assign_jitter([1, 2, 3], random.Random(1))
    jitter_b = assign_jitter([1, 2, 3], random.Random(1))
    assert jitter_a == jitter_b
    assert set(jitter_a.keys()) == {1, 2, 3}


def test_resolve_join_collisions_picks_lowest_jitter():
    jitter = {1: 0.9, 2: 0.1, 3: 0.5}
    assert resolve_join_collisions(jitter) == 2


def test_contending_children_all_eventually_join_shared_parent():
    net = Network(radio_range=6.0)
    net.add_node(Node(node_id=HUB_ID, position=(0.0, 0.0), role="hub"))
    net.add_node(Node(node_id=1, position=(5.0, 0.0), role="backbone"))  # P, 5.0 from hub
    # X, Y, Z are each ~5.0-3.0 from P (in range) but ~8.9-8.0 from the hub
    # (out of range), so they only ever hear P and must contend for it.
    net.add_node(Node(node_id=2, position=(8.0, 4.0), role="leaf"))
    net.add_node(Node(node_id=3, position=(8.0, -4.0), role="leaf"))
    net.add_node(Node(node_id=4, position=(8.0, 0.0), role="leaf"))

    run_wake_window(net, random.Random(7))

    for child_id in (2, 3, 4):
        assert net.nodes[child_id].parent_id == 1
        assert net.nodes[child_id].hop_count == 2
