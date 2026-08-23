import random
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


def assign_jitter(node_ids: list[int], rng: random.Random) -> dict[int, float]:
    return {node_id: rng.random() for node_id in node_ids}


def resolve_join_collisions(jitter: dict[int, float]) -> int:
    return min(jitter, key=jitter.get)


def run_wake_window(network: Network, rng: random.Random) -> None:
    for node in network.nodes.values():
        if node.node_id != HUB_ID:
            node.hop_count = None
            node.parent_id = None

    network.nodes[HUB_ID].hop_count = 0
    network.nodes[HUB_ID].parent_id = None

    parented = {HUB_ID}
    pending: dict[int, list[BeaconReceived]] = {}

    while True:
        for beaconer_id in parented:
            beaconer = network.nodes[beaconer_id]
            for neighbor_id in network.neighbors_of(beaconer_id):
                if neighbor_id in parented or neighbor_id in pending:
                    continue
                pending[neighbor_id] = [
                    BeaconReceived(
                        sender_id=beaconer_id,
                        hop_count=beaconer.hop_count,
                        rssi=network.rssi(neighbor_id, beaconer_id),
                    )
                ]

        if not pending:
            break

        groups: dict[int, list[int]] = {}
        for node_id, beacons in pending.items():
            parent_id = select_parent(beacons)
            groups.setdefault(parent_id, []).append(node_id)

        winners = []
        for parent_id, children in groups.items():
            jitter = assign_jitter(children, rng)
            winner_id = resolve_join_collisions(jitter)
            parent = network.nodes[parent_id]
            winner = network.nodes[winner_id]
            winner.parent_id = parent_id
            winner.hop_count = parent.hop_count + 1
            winners.append(winner_id)

        for winner_id in winners:
            del pending[winner_id]
        parented.update(winners)


@dataclass
class DataFrame:
    source_id: int
    needs_water: Optional[bool]
    battery_pct: float
    timestamp: int


def collect_data(network: Network, timestamp: int) -> dict[int, "DataFrame"]:
    frames: dict[int, DataFrame] = {}
    for node in network.nodes.values():
        if node.node_id == HUB_ID or node.hop_count is None:
            continue
        frames[node.node_id] = DataFrame(
            source_id=node.node_id,
            needs_water=node.needs_water,
            battery_pct=node.battery_pct,
            timestamp=timestamp,
        )
    return frames
