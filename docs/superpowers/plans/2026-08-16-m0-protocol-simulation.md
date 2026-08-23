# M0 Protocol Simulation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a software-only Python simulation of the self-organizing tree/collection protocol (wake scheduling, discovery/parent-selection, data relay, collision handling, provisioning) so the protocol design can be validated at 30-50 simulated nodes before any hardware is built.

**Architecture:** A `Network` holds `Node`s positioned in 2D space with a shared radio range; `sim/protocol.py` implements one "wake window" as a multi-hop beacon-propagation/parent-selection process with collision-aware joining; a `Simulator` runs repeated wake windows and collects `DataFrame`s per round; `sim/provisioning.py` implements the claim/unclaim pairing state machine. Everything is pure Python stdlib (`dataclasses`, `random`, `typing`) plus `pytest` for tests — no simulation framework, no networking library, since this milestone never touches real radio hardware.

**Tech Stack:** Python 3.11+, pytest. No external runtime dependencies.

**Spec:** `docs/superpowers/specs/2026-08-16-office-plant-swarm-design.md` (Section 4: Protocol Design, Section 5: Provisioning & Identity, Section 8: M0 deliverable)

## Global Constraints

- Simulation code lives under `sim/`, tests under `tests/`, both at repo root.
- Stdlib + pytest only — no external simulation/networking dependencies (YAGNI; this milestone validates logic, not wire format).
- Parent selection is always **hop-count first, RSSI as tiebreaker** (spec Section 4.2) — every task that touches parent selection must preserve this rule.
- `DataFrame` fields are exactly: `source_id`, `needs_water`, `battery_pct`, `timestamp` (spec Section 4.3) — byte-width packing is out of scope for M0 (that's a hardware-milestone concern), field *presence and semantics* are what M0 validates.
- Every wake window recomputes hop_count/parent from scratch (spec Section 4.2: "This re-evaluation happens every wake window") — this is what makes self-healing automatic; no task may special-case "if node was already parented, skip re-evaluation."
- `HUB_ID = 0` is the fixed sentinel for the hub/root node everywhere in the codebase.
- Every `run_wake_window` implementation must explicitly seed `network.nodes[HUB_ID].hop_count = 0` at the start of each call — it does not default to 0, and forgetting this seed makes every other node's hop count computation crash (caught by running the full task sequence against real Python during plan authoring, not just by inspection).

---

### Task 1: Project scaffolding & Node data model

**Files:**
- Create: `pyproject.toml`
- Create: `sim/__init__.py`
- Create: `sim/node.py`
- Test: `tests/test_node.py`

**Interfaces:**
- Produces: `HUB_ID: int = 0` constant in `sim/node.py`.
- Produces: `Node` dataclass in `sim/node.py`:
  - `node_id: int`
  - `position: tuple[float, float]`
  - `role: Literal["hub", "leaf", "backbone"]`
  - `battery_pct: float = 100.0`
  - `needs_water: Optional[bool] = None`
  - `hop_count: Optional[int] = None`
  - `parent_id: Optional[int] = None`
  - `claimed: bool = False`

- [x] **Step 1: Write the failing test**

```python
# tests/test_node.py
from sim.node import Node, HUB_ID


def test_node_defaults():
    n = Node(node_id=1, position=(0.0, 0.0), role="leaf")
    assert n.battery_pct == 100.0
    assert n.needs_water is None
    assert n.hop_count is None
    assert n.parent_id is None
    assert n.claimed is False


def test_hub_id_is_zero():
    assert HUB_ID == 0
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_node.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sim'`

- [x] **Step 3: Add project scaffolding**

```toml
# pyproject.toml
[tool.pytest.ini_options]
pythonpath = ["."]
```

```python
# sim/__init__.py
```

- [x] **Step 4: Implement the Node model**

```python
# sim/node.py
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
```

- [x] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_node.py -v`
Expected: PASS (2 passed)

- [x] **Step 6: Commit**

```bash
git add pyproject.toml sim/__init__.py sim/node.py tests/test_node.py
git commit -m "feat(sim): add project scaffolding and Node data model"
```

---

### Task 2: Network topology & RSSI model

**Files:**
- Create: `sim/network.py`
- Test: `tests/test_network.py`

**Interfaces:**
- Consumes: `Node`, `HUB_ID` from `sim/node.py`
- Produces: `Network` class in `sim/network.py`:
  - `Network(radio_range: float)`
  - `.nodes: dict[int, Node]`
  - `.add_node(node: Node) -> None`
  - `.remove_node(node_id: int) -> None`
  - `.distance(a_id: int, b_id: int) -> float`
  - `.rssi(a_id: int, b_id: int) -> float` (simplified: `-distance`; higher/less-negative = stronger signal, monotonic in distance — a deliberate simplification documented here, not real dBm; real RSSI arrives in a hardware milestone)
  - `.neighbors_of(node_id: int) -> list[int]` (all other nodes within `radio_range`, excluding self)

- [x] **Step 1: Write the failing test**

```python
# tests/test_network.py
from sim.node import Node
from sim.network import Network


def _net():
    net = Network(radio_range=10.0)
    net.add_node(Node(node_id=0, position=(0.0, 0.0), role="hub"))
    net.add_node(Node(node_id=1, position=(5.0, 0.0), role="leaf"))   # in range
    net.add_node(Node(node_id=2, position=(50.0, 0.0), role="leaf"))  # out of range
    return net


def test_distance():
    net = _net()
    assert net.distance(0, 1) == 5.0


def test_rssi_closer_is_stronger():
    net = _net()
    assert net.rssi(0, 1) > net.rssi(0, 2)


def test_neighbors_of_respects_radio_range():
    net = _net()
    assert net.neighbors_of(0) == [1]


def test_remove_node():
    net = _net()
    net.remove_node(1)
    assert 1 not in net.nodes
    assert net.neighbors_of(0) == []
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_network.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sim.network'`

- [x] **Step 3: Implement Network**

```python
# sim/network.py
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
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_network.py -v`
Expected: PASS (4 passed)

- [x] **Step 5: Commit**

```bash
git add sim/network.py tests/test_network.py
git commit -m "feat(sim): add Network topology and simplified RSSI model"
```

---

### Task 3: Beacon-based parent selection

**Files:**
- Create: `sim/protocol.py`
- Test: `tests/test_protocol_parent_selection.py`

**Interfaces:**
- Produces: `BeaconReceived` dataclass in `sim/protocol.py`: `sender_id: int`, `hop_count: int`, `rssi: float`
- Produces: `select_parent(beacons: list[BeaconReceived]) -> Optional[int]` — lowest `hop_count` wins; ties broken by highest `rssi`; returns `None` for an empty list.

- [x] **Step 1: Write the failing test**

```python
# tests/test_protocol_parent_selection.py
from sim.protocol import BeaconReceived, select_parent


def test_no_beacons_returns_none():
    assert select_parent([]) is None


def test_lowest_hop_count_wins():
    beacons = [
        BeaconReceived(sender_id=1, hop_count=2, rssi=-1.0),
        BeaconReceived(sender_id=2, hop_count=1, rssi=-9.0),
    ]
    assert select_parent(beacons) == 2


def test_tie_broken_by_best_rssi():
    beacons = [
        BeaconReceived(sender_id=1, hop_count=1, rssi=-9.0),
        BeaconReceived(sender_id=2, hop_count=1, rssi=-1.0),
    ]
    assert select_parent(beacons) == 2
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_protocol_parent_selection.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sim.protocol'`

- [x] **Step 3: Implement select_parent**

```python
# sim/protocol.py
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
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_protocol_parent_selection.py -v`
Expected: PASS (3 passed)

- [x] **Step 5: Commit**

```bash
git add sim/protocol.py tests/test_protocol_parent_selection.py
git commit -m "feat(sim): add beacon-based parent selection"
```

---

### Task 4: Single wake-window tree formation

**Files:**
- Modify: `sim/protocol.py`
- Test: `tests/test_protocol_wake_window.py`

**Interfaces:**
- Consumes: `Network` from `sim/network.py`; `HUB_ID` from `sim/node.py`; `BeaconReceived`, `select_parent` from `sim/protocol.py`
- Produces: `run_wake_window(network: Network) -> None` — mutates every non-hub node's `hop_count`/`parent_id` in place by propagating beacons outward from `HUB_ID` in BFS layers, using `select_parent` at each node. Resets all non-hub nodes' `hop_count`/`parent_id` to `None` at the start of every call (required for self-healing later).

- [x] **Step 1: Write the failing test**

```python
# tests/test_protocol_wake_window.py
from sim.node import Node, HUB_ID
from sim.network import Network
from sim.protocol import run_wake_window


def _chain_network():
    # hub -- A -- B, with hub and B out of each other's range
    net = Network(radio_range=10.0)
    net.add_node(Node(node_id=HUB_ID, position=(0.0, 0.0), role="hub"))
    net.add_node(Node(node_id=1, position=(9.0, 0.0), role="leaf"))
    net.add_node(Node(node_id=2, position=(18.0, 0.0), role="leaf"))
    net.add_node(Node(node_id=3, position=(100.0, 0.0), role="leaf"))  # isolated
    return net


def test_chain_forms_multi_hop_tree():
    net = _chain_network()
    run_wake_window(net)
    assert net.nodes[1].hop_count == 1
    assert net.nodes[1].parent_id == HUB_ID
    assert net.nodes[2].hop_count == 2
    assert net.nodes[2].parent_id == 1


def test_isolated_node_stays_unparented():
    net = _chain_network()
    run_wake_window(net)
    assert net.nodes[3].hop_count is None
    assert net.nodes[3].parent_id is None
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_protocol_wake_window.py -v`
Expected: FAIL with `ImportError: cannot import name 'run_wake_window'`

- [x] **Step 3: Implement run_wake_window**

```python
# sim/protocol.py (append)
from sim.network import Network
from sim.node import HUB_ID


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
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_protocol_wake_window.py -v`
Expected: PASS (2 passed)

- [x] **Step 5: Commit**

```bash
git add sim/protocol.py tests/test_protocol_wake_window.py
git commit -m "feat(sim): add multi-hop tree formation for a single wake window"
```

---

### Task 5: DATA payload and relay-to-hub collection

**Files:**
- Modify: `sim/protocol.py`
- Test: `tests/test_protocol_data.py`

**Interfaces:**
- Consumes: `Node`, `HUB_ID` from `sim/node.py`; `Network` from `sim/network.py`
- Produces: `DataFrame` dataclass in `sim/protocol.py`: `source_id: int`, `needs_water: Optional[bool]`, `battery_pct: float`, `timestamp: int`
- Produces: `collect_data(network: Network, timestamp: int) -> dict[int, DataFrame]` — one entry per non-hub node whose `hop_count is not None` (i.e., successfully attached to the tree this window); unattached/hub nodes excluded.

- [x] **Step 1: Write the failing test**

```python
# tests/test_protocol_data.py
from sim.node import Node, HUB_ID
from sim.network import Network
from sim.protocol import run_wake_window, collect_data


def test_collect_data_includes_only_attached_nodes():
    net = Network(radio_range=10.0)
    net.add_node(Node(node_id=HUB_ID, position=(0.0, 0.0), role="hub"))
    net.add_node(Node(node_id=1, position=(5.0, 0.0), role="leaf", needs_water=True, battery_pct=80.0))
    net.add_node(Node(node_id=2, position=(100.0, 0.0), role="leaf", needs_water=False))  # isolated

    run_wake_window(net)
    frames = collect_data(net, timestamp=42)

    assert set(frames.keys()) == {1}
    frame = frames[1]
    assert frame.source_id == 1
    assert frame.needs_water is True
    assert frame.battery_pct == 80.0
    assert frame.timestamp == 42
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_protocol_data.py -v`
Expected: FAIL with `ImportError: cannot import name 'collect_data'`

- [x] **Step 3: Implement DataFrame and collect_data**

```python
# sim/protocol.py (append)
from sim.node import Node


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
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_protocol_data.py -v`
Expected: PASS (1 passed)

- [x] **Step 5: Commit**

```bash
git add sim/protocol.py tests/test_protocol_data.py
git commit -m "feat(sim): add DATA payload and hub-side collection"
```

---

### Task 6: Randomized-backoff collision resolution

**Files:**
- Modify: `sim/protocol.py`
- Modify: `tests/test_protocol_wake_window.py:1` (update `run_wake_window` call sites for the new required `rng` argument)
- Test: `tests/test_protocol_collisions.py`

**Interfaces:**
- Consumes: `random.Random`
- Produces: `assign_jitter(node_ids: list[int], rng: random.Random) -> dict[int, float]`
- Produces: `resolve_join_collisions(jitter: dict[int, float]) -> int` — returns the `node_id` with the lowest jitter value.
- Modifies: `run_wake_window(network: Network, rng: random.Random) -> None` — **signature change**: now requires an `rng` argument. When multiple pending children pick the same parent in the same sub-tick, only the lowest-jitter one joins; the rest retry (fresh jitter) on the next sub-tick, guaranteeing everyone reachable still joins within the same window.

- [x] **Step 1: Write the failing tests**

```python
# tests/test_protocol_collisions.py
import random

from sim.node import Node, HUB_ID
from sim.network import Network
from sim.protocol import assign_jitter, resolve_join_collisions, run_wake_window


def test_assign_jitter_is_deterministic_for_a_given_seed():
    jitter_a = assign_jitter([1, 2, 3], random.Random(1))
    jitter_b = assign_jitter([1, 2, 3], random.Random(1))
    assert jitter_a == jitter_b
    assert set(jitter_a.keys()) == {1, 2, 3}


def test_resolve_join_collisions_picks_lowest_jitter():
    jitter = {1: 0.9, 2: 0.1, 3: 0.5}
    assert resolve_join_collisions(jitter) == 2


def test_contending_children_all_eventually_join_shared_parent():
    net = Network(radio_range=6.0)
    net.add_node(Node(node_id=HUB_ID, position=(0.0, 0.0), role="hub"))
    net.add_node(Node(node_id=1, position=(5.0, 0.0), role="backbone"))  # P, 5.0 from hub
    # X, Y, Z are each ~5.0-3.0 from P (in range) but ~8.9-8.0 from the hub
    # (out of range), so they only ever hear P and must contend for it.
    net.add_node(Node(node_id=2, position=(8.0, 4.0), role="leaf"))
    net.add_node(Node(node_id=3, position=(8.0, -4.0), role="leaf"))
    net.add_node(Node(node_id=4, position=(8.0, 0.0), role="leaf"))

    run_wake_window(net, random.Random(7))

    for child_id in (2, 3, 4):
        assert net.nodes[child_id].parent_id == 1
        assert net.nodes[child_id].hop_count == 2
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_protocol_collisions.py -v`
Expected: FAIL with `ImportError: cannot import name 'assign_jitter'`

- [x] **Step 3: Implement collision resolution and update run_wake_window**

```python
# sim/protocol.py — replace the existing run_wake_window with this version,
# and add assign_jitter / resolve_join_collisions above it
import random


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
```

Note: this replaces the frontier/BFS-layer loop from Task 4 with a sub-tick/pending-pool loop that additionally handles collisions. The observable behavior for non-contending topologies (Task 4's tests) is unchanged.

- [x] **Step 4: Update the Task 4 test file for the new signature**

```python
# tests/test_protocol_wake_window.py — add `import random` at the top,
# and change both calls from `run_wake_window(net)` to `run_wake_window(net, random.Random(0))`
```

- [x] **Step 5: Run the full test suite to verify everything passes**

Run: `pytest -v`
Expected: all tests pass, including the updated `test_protocol_wake_window.py` and the new `test_protocol_collisions.py`

- [x] **Step 6: Commit**

```bash
git add sim/protocol.py tests/test_protocol_wake_window.py tests/test_protocol_collisions.py
git commit -m "feat(sim): add randomized-backoff collision resolution to wake window"
```

---

### Task 7: Simulator — multi-round orchestration

**Files:**
- Create: `sim/simulator.py`
- Test: `tests/test_simulator.py`

**Interfaces:**
- Consumes: `Network` from `sim/network.py`; `run_wake_window`, `collect_data`, `DataFrame` from `sim/protocol.py`
- Produces: `Simulator` class in `sim/simulator.py`:
  - `Simulator(network: Network, seed: int = 0)`
  - `.round_number: int` (starts at 0, increments after each round)
  - `.history: list[dict[int, DataFrame]]`
  - `.run_round(self) -> dict[int, DataFrame]` — runs one wake window + data collection, appends to `history`, returns this round's frames

- [x] **Step 1: Write the failing test**

```python
# tests/test_simulator.py
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
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_simulator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sim.simulator'`

- [x] **Step 3: Implement Simulator**

```python
# sim/simulator.py
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
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_simulator.py -v`
Expected: PASS (2 passed)

- [x] **Step 5: Commit**

```bash
git add sim/simulator.py tests/test_simulator.py
git commit -m "feat(sim): add Simulator for multi-round orchestration"
```

---

### Task 8: Self-healing on node loss and node movement

**Files:**
- Test: `tests/test_self_healing.py`

No production code changes — this task validates spec Section 4.2's self-healing claim ("re-evaluation happens every wake window ... no manual resync step") using the `Network`, `Simulator` already built.

**Interfaces:**
- Consumes: `Node`, `HUB_ID` from `sim/node.py`; `Network` from `sim/network.py`; `Simulator` from `sim/simulator.py`

- [x] **Step 1: Write the failing test**

```python
# tests/test_self_healing.py
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
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_self_healing.py -v`
Expected: FAIL only if a prior task's implementation is wrong; if Tasks 1-7 are correct, this may pass immediately — run it anyway to confirm the *behavior*, not just import errors, is what's tested.

- [x] **Step 3: (No implementation needed — this task validates existing behavior)**

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_self_healing.py -v`
Expected: PASS (2 passed)

- [x] **Step 5: Commit**

```bash
git add tests/test_self_healing.py
git commit -m "test(sim): validate self-healing on node loss and movement"
```

---

### Task 9: Provisioning & pairing state machine

**Files:**
- Create: `sim/provisioning.py`
- Test: `tests/test_provisioning.py`

**Interfaces:**
- Consumes: `Network` from `sim/network.py`; `Node.claimed` from `sim/node.py`
- Produces: `RSSI_DISCOVERY_THRESHOLD: float = -8.0` constant in `sim/provisioning.py`
- Produces: `Hub` class in `sim/provisioning.py`:
  - `.claimed_names: dict[int, str]`
  - `.discoverable_nodes(network: Network, hub_id: int, threshold: float = RSSI_DISCOVERY_THRESHOLD) -> list[int]` — unclaimed nodes with `rssi(hub_id, node_id) >= threshold`
  - `.claim(network: Network, node_id: int, name: str) -> None` — sets `node.claimed = True`, records the name
  - `.factory_reset(network: Network, node_id: int) -> None` — sets `node.claimed = False`, removes the name

- [x] **Step 1: Write the failing test**

```python
# tests/test_provisioning.py
from sim.node import Node, HUB_ID
from sim.network import Network
from sim.provisioning import Hub


def _net():
    net = Network(radio_range=10.0)
    net.add_node(Node(node_id=HUB_ID, position=(0.0, 0.0), role="hub"))
    net.add_node(Node(node_id=1, position=(5.0, 0.0), role="leaf"))  # near, unclaimed
    net.add_node(Node(node_id=2, position=(100.0, 0.0), role="leaf"))  # far, unclaimed
    return net


def test_only_nearby_unclaimed_nodes_are_discoverable():
    net = _net()
    hub = Hub()
    assert hub.discoverable_nodes(net, HUB_ID) == [1]


def test_claim_removes_node_from_discovery_and_records_name():
    net = _net()
    hub = Hub()
    hub.claim(net, node_id=1, name="Ficus - meeting room")
    assert net.nodes[1].claimed is True
    assert hub.claimed_names[1] == "Ficus - meeting room"
    assert hub.discoverable_nodes(net, HUB_ID) == []


def test_factory_reset_makes_node_discoverable_again():
    net = _net()
    hub = Hub()
    hub.claim(net, node_id=1, name="Ficus - meeting room")
    hub.factory_reset(net, node_id=1)
    assert net.nodes[1].claimed is False
    assert 1 not in hub.claimed_names
    assert hub.discoverable_nodes(net, HUB_ID) == [1]
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_provisioning.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sim.provisioning'`

- [x] **Step 3: Implement Hub provisioning**

```python
# sim/provisioning.py
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
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_provisioning.py -v`
Expected: PASS (3 passed)

- [x] **Step 5: Commit**

```bash
git add sim/provisioning.py tests/test_provisioning.py
git commit -m "feat(sim): add provisioning and pairing state machine"
```

---

### Task 10: Scale validation — 30-50 simulated nodes

**Files:**
- Test: `tests/test_scale.py`

No production code changes — this is the M0 capstone validation described in spec Section 8 ("validate tree formation, self-healing on node loss/move, and collision behavior at 30-50 simulated nodes").

**Interfaces:**
- Consumes: `Node`, `HUB_ID` from `sim/node.py`; `Network` from `sim/network.py`; `Simulator` from `sim/simulator.py`

- [x] **Step 1: Write the failing test**

```python
# tests/test_scale.py
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
```

- [x] **Step 2: Run test to verify it fails or passes for the right reasons**

Run: `pytest tests/test_scale.py -v`
Expected: PASS if Tasks 1-9 are implemented correctly — this task's purpose is to exercise the existing implementation at scale and catch any bug that only manifests with more nodes/collisions, so a pass here is the desired outcome, not evidence the test is trivial (the geometric ground-truth comparison and tree-consistency invariant would fail on a buggy implementation).

- [x] **Step 3: (No implementation needed — this task validates existing behavior at scale)**

- [x] **Step 4: Run the full test suite one final time**

Run: `pytest -v`
Expected: all tests across every task pass

- [x] **Step 5: Commit**

```bash
git add tests/test_scale.py
git commit -m "test(sim): validate tree formation and self-healing at 30-50 node scale"
```
