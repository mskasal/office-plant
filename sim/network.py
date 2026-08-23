import math

from sim.node import Node


class Network:
    def __init__(self, radio_range: float):
        self.radio_range = radio_range
        self.nodes: dict[int, Node] = {}

    def add_node(self, node: Node) -> None:
        self.nodes[node.node_id] = node

    def remove_node(self, node_id: int) -> None:
        del self.nodes[node_id]

    def distance(self, a_id: int, b_id: int) -> float:
        ax, ay = self.nodes[a_id].position
        bx, by = self.nodes[b_id].position
        return math.hypot(ax - bx, ay - by)

    def rssi(self, a_id: int, b_id: int) -> float:
        return -self.distance(a_id, b_id)

    def neighbors_of(self, node_id: int) -> list[int]:
        return [
            other_id
            for other_id in self.nodes
            if other_id != node_id and self.distance(node_id, other_id) <= self.radio_range
        ]
