from dataclasses import dataclass
from typing import Optional

from sim.network import Network
from sim.node import HUB_ID


@dataclass
class BeaconReceived:
    sender_id: int
    hop_count: int
    rssi: float


def select_parent(beacons: list[BeaconReceived]) -> Optional[int]:
    if not beacons:
        return None
    best = min(beacons, key=lambda b: (b.hop_count, -b.rssi))
    return best.sender_id


def run_wake_window(network: Network) -> None:
    for node in network.nodes.values():
        if node.node_id != HUB_ID:
            node.hop_count = None
            node.parent_id = None

    network.nodes[HUB_ID].hop_count = 0
    network.nodes[HUB_ID].parent_id = None

    frontier = {HUB_ID}
    while frontier:
        candidates: dict[int, list[BeaconReceived]] = {}
        for beaconer_id in frontier:
            beaconer = network.nodes[beaconer_id]
            for neighbor_id in network.neighbors_of(beaconer_id):
                neighbor = network.nodes[neighbor_id]
                if neighbor_id == HUB_ID or neighbor.parent_id is not None:
                    continue
                candidates.setdefault(neighbor_id, []).append(
                    BeaconReceived(
                        sender_id=beaconer_id,
                        hop_count=beaconer.hop_count,
                        rssi=network.rssi(neighbor_id, beaconer_id),
                    )
                )
        if not candidates:
            break
        newly_parented = set()
        for node_id, beacons in candidates.items():
            parent_id = select_parent(beacons)
            node = network.nodes[node_id]
            node.parent_id = parent_id
            node.hop_count = network.nodes[parent_id].hop_count + 1
            newly_parented.add(node_id)
        frontier = newly_parented
