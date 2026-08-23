from sim.node import Node, HUB_ID
from sim.network import Network
from sim.simulator import Simulator


def test_heals_by_becoming_unreachable_when_only_relay_is_removed():
    net = Network(radio_range=10.0)
    net.add_node(Node(node_id=HUB_ID, position=(0.0, 0.0), role="hub"))
    net.add_node(Node(node_id=1, position=(9.0, 0.0), role="backbone"))
    net.add_node(Node(node_id=2, position=(18.0, 0.0), role="leaf"))  # only reachable via 1

    sim = Simulator(net, seed=0)
    sim.run_round()
    assert net.nodes[2].hop_count == 2
    assert net.nodes[2].parent_id == 1

    net.remove_node(1)
    frames = sim.run_round()
    assert net.nodes[2].hop_count is None
    assert 2 not in frames


def test_heals_by_reparenting_when_a_node_moves_closer_to_hub():
    net = Network(radio_range=10.0)
    net.add_node(Node(node_id=HUB_ID, position=(0.0, 0.0), role="hub"))
    net.add_node(Node(node_id=1, position=(9.0, 0.0), role="backbone"))
    net.add_node(Node(node_id=2, position=(18.0, 0.0), role="leaf"))  # routes via 1

    sim = Simulator(net, seed=0)
    sim.run_round()
    assert net.nodes[2].hop_count == 2
    assert net.nodes[2].parent_id == 1

    net.nodes[2].position = (5.0, 0.0)  # moved into direct hub range
    sim.run_round()
    assert net.nodes[2].hop_count == 1
    assert net.nodes[2].parent_id == HUB_ID
