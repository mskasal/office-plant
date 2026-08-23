from sim.node import Node, HUB_ID
from sim.network import Network
from sim.provisioning import Hub


def _net():
    net = Network(radio_range=10.0)
    net.add_node(Node(node_id=HUB_ID, position=(0.0, 0.0), role="hub"))
    net.add_node(Node(node_id=1, position=(5.0, 0.0), role="leaf"))  # near, unclaimed
    net.add_node(Node(node_id=2, position=(100.0, 0.0), role="leaf"))  # far, unclaimed
    return net


def test_only_nearby_unclaimed_nodes_are_discoverable():
    net = _net()
    hub = Hub()
    assert hub.discoverable_nodes(net, HUB_ID) == [1]


def test_claim_removes_node_from_discovery_and_records_name():
    net = _net()
    hub = Hub()
    hub.claim(net, node_id=1, name="Ficus - meeting room")
    assert net.nodes[1].claimed is True
    assert hub.claimed_names[1] == "Ficus - meeting room"
    assert hub.discoverable_nodes(net, HUB_ID) == []


def test_factory_reset_makes_node_discoverable_again():
    net = _net()
    hub = Hub()
    hub.claim(net, node_id=1, name="Ficus - meeting room")
    hub.factory_reset(net, node_id=1)
    assert net.nodes[1].claimed is False
    assert 1 not in hub.claimed_names
    assert hub.discoverable_nodes(net, HUB_ID) == [1]
