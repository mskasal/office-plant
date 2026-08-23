import random

from sim.node import Node, HUB_ID
from sim.network import Network
from sim.protocol import run_wake_window


def _chain_network():
    # hub -- A -- B, with hub and B out of each other's range
    net = Network(radio_range=10.0)
    net.add_node(Node(node_id=HUB_ID, position=(0.0, 0.0), role="hub"))
    net.add_node(Node(node_id=1, position=(9.0, 0.0), role="leaf"))
    net.add_node(Node(node_id=2, position=(18.0, 0.0), role="leaf"))
    net.add_node(Node(node_id=3, position=(100.0, 0.0), role="leaf"))  # isolated
    return net


def test_chain_forms_multi_hop_tree():
    net = _chain_network()
    run_wake_window(net, random.Random(0))
    assert net.nodes[1].hop_count == 1
    assert net.nodes[1].parent_id == HUB_ID
    assert net.nodes[2].hop_count == 2
    assert net.nodes[2].parent_id == 1


def test_isolated_node_stays_unparented():
    net = _chain_network()
    run_wake_window(net, random.Random(0))
    assert net.nodes[3].hop_count is None
    assert net.nodes[3].parent_id is None
