import random

from sim.network import Network
from sim.protocol import DataFrame, collect_data, run_wake_window


class Simulator:
    def __init__(self, network: Network, seed: int = 0):
        self.network = network
        self.rng = random.Random(seed)
        self.round_number = 0
        self.history: list[dict[int, DataFrame]] = []

    def run_round(self) -> dict[int, DataFrame]:
        run_wake_window(self.network, self.rng)
        frames = collect_data(self.network, timestamp=self.round_number)
        self.history.append(frames)
        self.round_number += 1
        return frames
