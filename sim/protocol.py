from dataclasses import dataclass
from typing import Optional


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
