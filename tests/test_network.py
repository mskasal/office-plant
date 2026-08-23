from sim.node import Node
from sim.network import Network


def _net():
    net = Network(radio_range=10.0)
    net.add_node(Node(node_id=0, position=(0.0, 0.0), role="hub"))
    net.add_node(Node(node_id=1, position=(5.0, 0.0), role="leaf"))   # in range
    net.add_node(Node(node_id=2, position=(50.0, 0.0), role="leaf"))  # out of range
    return net


def test_distance():
    net = _net()
    assert net.distance(0, 1) == 5.0


def test_rssi_closer_is_stronger():
    net = _net()
    assert net.rssi(0, 1) > net.rssi(0, 2)


def test_neighbors_of_respects_radio_range():
    net = _net()
    assert net.neighbors_of(0) == [1]


def test_remove_node():
    net = _net()
    net.remove_node(1)
    assert 1 not in net.nodes
    assert net.neighbors_of(0) == []
