from sim.network import Network

RSSI_DISCOVERY_THRESHOLD = -8.0


class Hub:
    def __init__(self):
        self.claimed_names: dict[int, str] = {}

    def discoverable_nodes(
        self, network: Network, hub_id: int, threshold: float = RSSI_DISCOVERY_THRESHOLD
    ) -> list[int]:
        return [
            node.node_id
            for node in network.nodes.values()
            if node.node_id != hub_id
            and not node.claimed
            and network.rssi(hub_id, node.node_id) >= threshold
        ]

    def claim(self, network: Network, node_id: int, name: str) -> None:
        network.nodes[node_id].claimed = True
        self.claimed_names[node_id] = name

    def factory_reset(self, network: Network, node_id: int) -> None:
        network.nodes[node_id].claimed = False
        self.claimed_names.pop(node_id, None)
