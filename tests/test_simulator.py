from sim.node import Node, HUB_ID
from sim.network import Network
from sim.simulator import Simulator


def _chain_network():
    net = Network(radio_range=10.0)
    net.add_node(Node(node_id=HUB_ID, position=(0.0, 0.0), role="hub"))
    net.add_node(Node(node_id=1, position=(9.0, 0.0), role="leaf", needs_water=True))
    return net


def test_run_round_returns_and_stores_data_frames():
    sim = Simulator(_chain_network(), seed=0)
    frames = sim.run_round()

    assert frames[1].source_id == 1
    assert frames[1].needs_water is True
    assert sim.round_number == 1
    assert sim.history == [frames]


def test_multiple_rounds_accumulate_history():
    sim = Simulator(_chain_network(), seed=0)
    sim.run_round()
    sim.run_round()
    assert sim.round_number == 2
    assert len(sim.history) == 2
