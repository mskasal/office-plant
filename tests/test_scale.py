import random

from sim.node import Node, HUB_ID
from sim.network import Network
from sim.simulator import Simulator

RADIO_RANGE = 12.0
GRID_SPACING = 8.0  # < RADIO_RANGE so the grid is connected by construction


def _build_grid_network(n_nodes: int, seed: int) -> Network:
    rng = random.Random(seed)
    net = Network(radio_range=RADIO_RANGE)
    net.add_node(Node(node_id=HUB_ID, position=(0.0, 0.0), role="hub"))

    side = 1
    while side * side < n_nodes:
        side += 1

    node_id = 1
    for row in range(side):
        for col in range(side):
            if node_id > n_nodes:
                break
            jitter_x = rng.uniform(-1.0, 1.0)
            jitter_y = rng.uniform(-1.0, 1.0)
            position = (col * GRID_SPACING + jitter_x, row * GRID_SPACING + jitter_y)
            net.add_node(Node(node_id=node_id, position=position, role="leaf", needs_water=False))
            node_id += 1
    return net


def _geometrically_reachable_ids(net: Network) -> set[int]:
    """Ground truth: BFS over the raw radio-range adjacency graph, independent of the protocol."""
    visited = {HUB_ID}
    frontier = [HUB_ID]
    while frontier:
        current = frontier.pop()
        for neighbor_id in net.neighbors_of(current):
            if neighbor_id not in visited:
                visited.add(neighbor_id)
                frontier.append(neighbor_id)
    visited.discard(HUB_ID)
    return visited


def _assert_tree_is_consistent(net: Network, expected_reachable: set[int]):
    attached = {n.node_id for n in net.nodes.values() if n.node_id != HUB_ID and n.hop_count is not None}
    assert attached == expected_reachable
    for node in net.nodes.values():
        if node.node_id == HUB_ID or node.hop_count is None:
            continue
        parent = net.nodes[node.parent_id]
        assert node.hop_count == parent.hop_count + 1


def test_30_nodes_all_geometrically_reachable_nodes_join_tree():
    net = _build_grid_network(30, seed=123)
    expected = _geometrically_reachable_ids(net)
    sim = Simulator(net, seed=123)
    sim.run_round()
    _assert_tree_is_consistent(net, expected)


def test_50_nodes_all_geometrically_reachable_nodes_join_tree():
    net = _build_grid_network(50, seed=456)
    expected = _geometrically_reachable_ids(net)
    sim = Simulator(net, seed=456)
    sim.run_round()
    _assert_tree_is_consistent(net, expected)


def test_self_heals_after_removing_a_relay_node_mid_tree():
    net = _build_grid_network(30, seed=123)
    sim = Simulator(net, seed=123)
    sim.run_round()

    parents_used = {n.parent_id for n in net.nodes.values() if n.node_id != HUB_ID and n.parent_id is not None}
    relay_id = next(iter(parents_used - {HUB_ID}))
    net.remove_node(relay_id)

    expected = _geometrically_reachable_ids(net)
    sim.run_round()
    _assert_tree_is_consistent(net, expected)
