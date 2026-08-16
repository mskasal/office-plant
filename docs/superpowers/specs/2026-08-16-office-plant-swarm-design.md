# Office Plant Swarm — Design Spec

Status: Draft for review
Date: 2026-08-16

## 1. Product Overview

### Problem

The office has 30 (growing to 50+) plants spread across multiple rooms.
Manually checking each one for dryness doesn't scale — it's tedious and
plants get missed. There's no existing sensor infrastructure and no
prior codebase; this is a greenfield hardware + firmware + software
project.

### Goals (v1)

- A battery/solar-powered sensor sits in each plant's pot and reports
  whether that plant needs water.
- Sensors self-organize into a multi-hop mesh so a single hub can
  reach every plant even across rooms separated by walls/glass doors,
  without needing a sensor-to-hub direct radio link.
- Setup is "unbox, place near hub, tap to name" — no manual network
  configuration.
- A single person can open a local web page and see, for every named
  plant, whether it needs water.
- The system must not require per-node cost anywhere near €20 — target
  €10-15 all-in per sensor node.
- The design must not need code changes to grow from 30 to 50+ nodes.

### Non-Goals (v1 — explicitly deferred)

- Push notifications / alerts (email, Slack, etc.) — v2.
- An always-on physical hub screen — v2.
- On-demand ("wake the mesh right now") refresh — documented as a
  future extension (Section 10), not built in v1.
- Multi-hub / multi-site deployments.
- Firmware OTA update mechanism.

## 2. System Architecture

```
[Sensor Leaf Node]  [Sensor Leaf Node]  [Backbone/Relay Node]
        \                  |                    /
         \                 |                   /
          \                |                  /
        (self-organizing multi-hop 802.15.4 mesh)
                            |
                  [Hub-Radio Dongle: ESP32-C6]
                            | USB/serial
                  [Raspberry Pi: dashboard + storage]
                            |
                    (local web browser)
```

Three physical roles, one firmware image:

- **Sensor leaf node**: battery+solar powered, has a soil moisture
  sensor, sleeps almost all the time, wakes on its own schedule to
  sense and report.
- **Backbone/relay node**: same firmware, no sensor attached (or
  sensor ignored via config), typically has a stronger antenna/PA
  and/or mains power, placed to bridge weak spots (e.g., between
  rooms). Every node — leaf or backbone — already relays for its
  children as an inherent property of the tree protocol; "backbone"
  is a hardware/placement choice, not a special code path.
- **Hub-radio dongle**: an ESP32-C6 acting as the mesh's root, running
  the same firmware family but in "root" role. Talks to the mesh over
  802.15.4 and to the Raspberry Pi over USB/serial.

The Raspberry Pi is not part of the mesh's radio protocol at all — it
only sees the root node's serial output. This keeps the mesh protocol
implementation self-contained and testable independent of the hub
software.

## 3. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Node MCU | ESP32-C6 | Native 802.15.4 radio (better wall/glass penetration than WiFi at similar power), cheap (~€3-6/module), mass-produced, deep-sleep in the single-digit µA range. |
| Node firmware framework | ESP-IDF (C) | Gives raw access to the 802.15.4 radio (`esp_ieee802154` component) needed to run our own protocol instead of a full Zigbee/Thread stack, plus mature deep-sleep/RTC-timer APIs. |
| Moisture sensing | Capacitive soil moisture sensor (analog) | Corrosion-resistant vs. resistive probes, long field life. |
| Node power | LiPo battery + small solar panel + integrated solar-LiPo charge/protection circuit | Matches the "rechargeable via ambient/window light" requirement. |
| Hub-radio dongle | ESP32-C6 (same base hardware as nodes, "root" firmware role) | Reuses the same radio stack; avoids needing a second radio technology on the Pi. |
| Hub compute | Raspberry Pi (Zero 2 W class is sufficient) | Cheap, runs Linux, USB host for the dongle, always-on. |
| Hub backend | Python/FastAPI as a starting default; not finalized | Simple to get a v1 dashboard working. Revisit at M3 if efficiency matters more than dev speed by then (e.g., a lighter framework or a compiled language) — deliberately deferred, not a hard commitment. |
| Hub storage | SQLite | Single file, zero-ops, more than sufficient for tens of nodes reporting 1-2x/day. |
| Hub frontend (v1) | Server-rendered HTML (Jinja2) + minimal JS | "Start simple" — no build step, no framework needed for a pull-to-view dashboard. |

## 4. Protocol Design

### 4.1 Duty cycle & scheduling

- Every node has its own RTC-backed timer and wakes **autonomously**
  on a schedule it already knows — no signal from the hub is needed to
  trigger a wake, so nodes never need to keep a radio listening for a
  wake command.
- Default schedule: 1-2 wake windows per day (e.g., ~08:00 and
  ~20:00), configurable.
- **The hub is in charge of schedule/config, but only ever speaks
  during a window a node itself opened.** Each time a node wakes,
  reports, and successfully reaches the hub (directly or via relay),
  the response piggybacks any updated config (e.g., new wake interval,
  threshold tuning). This gives centralized control with zero added
  standby cost.
- During a wake window a node: senses (if it has a sensor) → refreshes
  its view of neighbors/parent → transmits its data upward (and
  relays any queued child data) → applies any config pushed back down
  → sleeps.

### 4.2 Discovery & tree formation

- On waking, a node listens briefly for **BEACON** frames from
  neighbors already awake in this window. A beacon advertises: sender
  ID, hop-count-to-hub, and a signal-quality indicator (RSSI).
- The node selects a parent by **lowest hop-count first, RSSI as
  tiebreaker**, then sends a short **JOIN** to confirm/refresh that
  parent link. This re-evaluation happens every wake window, so the
  tree self-heals automatically if a node is moved, added, or drops
  out (dead battery, powered off) — no manual resync step.
- The hub-radio dongle is hop-count 0 and always beacons first in each
  window; hop-count propagates outward from there.

### 4.3 Data payload (DATA frame)

| Field | Size | Notes |
|---|---|---|
| Source node ID | 2 bytes | 16-bit address, assigned at pairing time (see 4.5) |
| Moisture status | 1 byte | Needs-water flag + raw ADC reading (sensor nodes only) |
| Battery/power level | 1 byte | For maintenance visibility (low-battery flagging) |
| Timestamp | 4 bytes | Node's local clock, corrected against hub time each check-in |

Relay nodes forward child DATA frames unmodified, prepending nothing
but their own routing metadata at the radio layer — the hub only cares
about the original source ID.

### 4.4 Collision avoidance

Traffic is sparse (a handful of nodes, 1-2 windows/day), so a simple
randomized backoff before transmit (listen-before-talk + small random
delay) is sufficient — no need for a scheduled TDMA slot scheme.

### 4.5 Addressing & scaling

- Nodes are identified long-term by a 16-bit short address, assigned
  by the hub at pairing time (see Section 5). Their factory-unique
  64-bit ID (e.g., radio MAC) is only used during the pairing
  handshake itself.
- 16-bit address space supports far beyond 50 nodes; no part of the
  protocol assumes a fixed node count. Growing from 30 to 50+ nodes
  requires no protocol or firmware changes.

## 5. Provisioning & Identity

- **Default state**: a new (or factory-reset) node boots into
  **pairing mode** — radio listening continuously/frequently rather
  than on the power-saving schedule, and advertising itself as
  unclaimed.
- **Setup flow**: place new nodes near the hub → open the hub web
  page → unclaimed nodes above a connection-strength threshold appear
  in a discovery list → tap one → hub tells that specific node to
  blink an LED → user visually confirms the physical node → user
  names it (e.g., "Ficus — meeting room corner") → hub assigns it a
  16-bit address and marks it claimed.
- On claim, the node stores the hub's ID, switches to the normal
  power-saving scheduled mode, and stops advertising itself as
  discoverable (so it can't be picked up by another hub or re-listed
  by accident).
- Nodes can then be physically relocated to their real spot; the tree
  protocol (4.2) re-forms around them automatically on the next wake.
- **Factory reset**: holding a button for ~5s returns a node to
  pairing mode (unclaimed, continuously listening), for re-pairing or
  handing off to a different hub.

## 6. Hub / Dashboard (v1 scope)

Data model (SQLite):

- `nodes`: id (16-bit address), name, role (leaf/backbone), claimed_at,
  last_seen_at, battery_level
- `readings`: node_id, timestamp, moisture_status

Dashboard (v1): a single local page listing every named node with its
last-known moisture status, battery level, and last-seen time — pull
model, refreshed when you open the page. A node that hasn't reported
in more than ~2x its expected interval is shown as "offline" rather
than silently stale.

Deferred to v2 (not built now, but the FastAPI/SQLite split is chosen
so these can be added without a rewrite): push alerts, an always-on
screen UI, on-demand mesh refresh.

## 7. Scalability & Reliability Considerations

- Self-organizing tree (4.2) means adding nodes 30 → 50+ is a
  deployment action, not a code change.
- Backbone/relay nodes are the mechanism for covering weak spots
  (rooms behind glass/thin walls); these are a placement and BOM
  decision made empirically during pilot deployment (Section 8, M5/M7),
  not something solvable in the abstract.
- Offline detection (Section 6) is the v1 mechanism for noticing a
  dead battery or an isolated node — no push alert yet, but visible on
  the dashboard.

## 8. Milestone Roadmap

Each milestone has a clear goal and is independently verifiable before
moving to the next.

- **M0 — Protocol spec & simulation.** Formalize packet formats and
  the wake/discovery/parent-selection state machine from Section 4.
  Build a software-only simulation (no hardware) to validate tree
  formation, self-healing on node loss/move, and collision behavior
  at 30-50 simulated nodes before any hardware is involved.
- **M1 — Single-node firmware skeleton.** ESP-IDF project for one
  ESP32-C6: deep sleep + RTC wake, moisture sensor read, radio
  init/send. Goal: confirm real measured power draw matches the solar
  budget assumption.
- **M2 — Two-node link.** Two physical nodes exchange BEACON/JOIN/DATA
  over real 802.15.4 radio; validate the protocol from M0 against real
  RF behavior, including range/penetration through one wall.
- **M3 — Hub software.** Hub-radio dongle (ESP32-C6, root role) + Pi
  running FastAPI/SQLite/dashboard; ingest real data from the M2 pair
  into a working dashboard showing plant identity + moisture status.
- **M4 — Provisioning flow.** Implement pairing mode, the
  discover/tap/blink/name flow, factory reset, and ownership binding
  end-to-end.
- **M5 — Multi-hop mesh at scale.** Expand to several physical nodes
  across multiple rooms; validate multi-hop routing, self-healing on
  move/power-loss, and the hub-governed config push.
- **M6 — Hardware finalization.** Lock the BOM for both node variants
  (sensor leaf vs. backbone) using real power numbers from M1-M5; size
  solar/battery; finalize enclosure.
- **M7 — Pilot deployment.** Deploy across the real office (target 30
  nodes), run for at least two weeks, tune schedule/thresholds, and
  identify dead zones needing backbone nodes.

## 9. Testing / Verification Strategy

- M0 is validated entirely in software (simulation), which is the
  cheapest place to catch protocol-logic bugs before hardware is
  involved.
- M1-M2 are validated on real hardware bench tests, comparing measured
  power draw and radio range against the assumptions in Sections 3-4.
- M3-M5 are validated by observing the dashboard against known ground
  truth (manually checking the plants the dashboard claims are
  dry/wet).
- M7 is the real-world acceptance test: does the dashboard match
  reality across the full office for two weeks with no missed
  waterings attributable to the system.

## 10. Open Questions / Future Work

- **On-demand wake**: true instant "refresh now" conflicts with the
  near-zero standby power design. A documented future option is
  letting backbone/relay nodes (which may be mains-powered) run a
  low-power periodic paging listen so the hub can reach *them*
  on-demand, while battery/solar leaf nodes stay on the cheap
  scheduled-only wake.
- **Always-on screen hub**: mentioned as a "later" want; FastAPI
  backend is structured so a screen client can poll the same API the
  browser dashboard uses.
- **Push alerts**: deferred; would hang off the same offline/dry
  detection already in the v1 data model.
