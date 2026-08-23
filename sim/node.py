from dataclasses import dataclass
from typing import Literal, Optional

HUB_ID = 0

NodeRole = Literal["hub", "leaf", "backbone"]


@dataclass
class Node:
    node_id: int
    position: tuple[float, float]
    role: NodeRole
    battery_pct: float = 100.0
    needs_water: Optional[bool] = None
    hop_count: Optional[int] = None
    parent_id: Optional[int] = None
    claimed: bool = False
