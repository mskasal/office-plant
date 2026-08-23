# M4 Provisioning Flow — Implementation Plan

**Goal:** Pairing mode by default, the discover → tap → blink → name flow, factory reset, and ownership binding — end to end (spec Section 5).

**Spec:** `docs/superpowers/specs/2026-08-16-office-plant-swarm-design.md` (Section 5), `docs/superpowers/plans/2026-08-16-m0-protocol-simulation.md` (`sim/provisioning.py`'s `Hub` class — the design this milestone makes real).

Lighter-weight plan: structure and decisions, not embedded source code.

## What M1-M3 already provide

Radio send/receive (M1), root/leaf roles (M2), and the dongle↔Pi serial bridge + dashboard (M3). M4 adds new frame types, persistent node identity, and the hub-side claim/discover logic.

## Decisions

### New frame types, reusing the existing 5-byte "addr-pair" shape

M1's `join_frame_t` (`sender_id` + `target_parent_id`, 5 bytes total) is structurally identical to what BLINK and CLAIM need — reuse the same layout with different type bytes and reinterpreted field meaning, rather than adding new structs:

- `FRAME_TYPE_BLINK` (hub → node): fields reinterpreted as `(hub_id, target_node_id)`. Node receiving this with `target_node_id` matching its own factory ID blinks an LED for ~3s.
- `FRAME_TYPE_CLAIM` (hub → node): fields reinterpreted as `(assigned_short_address, hub_id)`. A node in pairing mode receiving this persists `hub_id` + its new `short_address`, sets `claimed = true`, and switches from pairing-mode behavior to the normal scheduled wake cycle.

Both are added to `firmware/components/protocol/protocol_frame.h` (C) and `hub/protocol_frame.py` (Python) — the same two files M3 already established as the single source of truth for wire format, kept in sync.

### Persistent node identity — NVS, not RTC memory

`claimed`, `hub_id`, and `short_address` must survive a full power loss (battery swap, not just deep sleep) — M1's `RTC_DATA_ATTR` boot counter does *not* survive that. **Decision:** use ESP-IDF's NVS (non-volatile storage) API instead. New module `firmware/main/node_identity.c/h`:
```c
bool node_identity_is_claimed(void);
void node_identity_set_claimed(uint16_t hub_id, uint16_t short_address);
void node_identity_factory_reset(void);
```
Backed by `nvs_flash_init()` + `nvs_get_u8`/`nvs_set_u8`/`nvs_get_u16`/`nvs_set_u16` calls at execution time — a well-documented, standard ESP-IDF pattern, not a novel design.

### Pairing-mode wake behavior

An unclaimed node does **not** use M1's sparse 1-2x/day schedule — it wakes frequently (e.g., listens 500ms every 2s) so it responds quickly during setup, per the spec's "seamless setup" requirement. On receiving a valid `CLAIM` frame, it immediately switches to the normal scheduled cycle. This is a real behavioral fork in `main.c`'s top-level loop: `if (!node_identity_is_claimed()) { pairing_mode_loop(); } else { scheduled_wake_cycle(); }` (the latter being M1/M2's existing behavior, unchanged).

### Discovery filtering — hub-side, not firmware-side

The firmware doesn't decide who's "close enough" — it just always responds while unclaimed. The hub (`hub/provisioning.py`) filters by the RSSI value already included in every `RX <hex> <rssi>` line from M3's serial bridge, using the same threshold concept as `sim/provisioning.py`'s `RSSI_DISCOVERY_THRESHOLD` from M0 (the exact real-world dBm value needs recalibrating against real RSSI readings once M2's range test has run — M0's simulated value was never meant to be the production constant).

### Factory reset — hardware button

Long-press (~5s) on a GPIO — reuse the ESP32-C6 dev board's existing BOOT button (commonly GPIO9) rather than adding a dedicated button to the BOM, keeping cost down per the spec's cost constraint. Long-press detection via polling `gpio_get_level` in the pairing-mode/scheduled loop, or a GPIO interrupt — exact mechanism decided at execution time; the requirement (5s hold → `node_identity_factory_reset()` → reboot into pairing mode) is what's fixed here.

## Components

- `firmware/main/node_identity.c/h` — NVS-backed claim state (above).
- `firmware/main/main.c` — branch between pairing-mode loop and scheduled cycle based on `node_identity_is_claimed()`; handle incoming BLINK (drive an LED GPIO) and CLAIM (persist + switch mode) frames.
- `hub/provisioning.py` — `Hub` class mirroring `sim/provisioning.py`'s method names/shapes from M0 (`discoverable_nodes`, `claim`, `factory_reset`), now backed by the real `nodes` SQLite table and issuing real `BLINK`/`CLAIM` frames via M3's serial bridge `TX` command instead of mutating in-memory state.
- Dashboard addition: a "Discover" page — lists currently-discoverable unclaimed nodes (polls `hub/provisioning.py`), a tap action sends `BLINK`, a name field + submit calls `claim()`.

## Task list

1. Add `FRAME_TYPE_BLINK`/`FRAME_TYPE_CLAIM` to both `protocol_frame.h` and `protocol_frame.py`, keeping them in sync (this is the same correctness-critical cross-language concern M3 flagged for the DATA/BEACON/JOIN types).
2. `node_identity.c/h` — NVS claim-state module.
3. `main.c` — pairing-mode loop, BLINK/CLAIM frame handling, mode branch.
4. Factory-reset button handling.
5. `hub/provisioning.py` — port of `sim/provisioning.py`'s design onto real SQLite + real frame sends.
6. Dashboard "Discover" page.
7. End-to-end bench test: factory-fresh node near the dongle → appears in the Discover page → tap → physically blinks → name it → confirm it stops appearing as discoverable and starts reporting on the normal schedule. Hold the reset button → confirm it reappears as discoverable.

## Verification

Step 5 (`hub/provisioning.py`) is a near-direct port of M0's already-verified `sim/provisioning.py` logic and should get the same host-test treatment (the three test cases from `tests/test_provisioning.py`, adapted to real SQLite). Steps 1-4 need the ESP-IDF toolchain and hardware; step 7 needs the full physical chain from M3 plus a factory-fresh node.

### Implementation status (as of this commit)

- ✅ **Task 1** (frame types) — `FRAME_TYPE_BLINK`/`FRAME_TYPE_CLAIM` added exactly as decided (reusing JOIN's 5-byte shape), kept in sync across the C header/impl and `hub/protocol_frame.py`. **Also added `FRAME_TYPE_ANNOUNCE`, not in the plan's task list** — a real gap found while implementing: BLINK/CLAIM are hub-initiated and require already knowing which node to target, but nothing in the plan's design has an unclaimed node transmitting anything for the hub to discover in the first place. ANNOUNCE (unclaimed node → hub, periodic factory_id presence) closes that gap. All host-tested: 12 C checks, 11 pytest cases.
- ✅ **Task 5** (`hub/provisioning.py`) — implemented and host-tested per the plan's own instruction (7 pytest cases, real SQLite). `discoverable_nodes` is necessarily different from the sim: it comes from recently-observed ANNOUNCE sightings (RSSI + staleness filtered), not simulated network positions, since a real unclaimed node has no row anywhere until claimed.
- ✅ **Task 6** (Discover dashboard page) — implemented and host-tested (4 new `test_hub_api.py` cases via FastAPI's TestClient): lists announcing factory IDs, Blink/Claim actions wired through `hub/provisioning.py`.
- ⚠️ **Tasks 2-4** (`node_identity.c/h`, `pairing_mode.c/h`, `factory_reset_button.c/h`, `main.c` dispatch) are written against real ESP-IDF NVS/GPIO/deep-sleep-wake APIs but not run through `idf.py build` — same ESP-IDF/hardware constraint as M1-M3. Two implementation decisions filled real gaps the plan left open:
  - **Factory-ID width mismatch**: the plan says BLINK/CLAIM target a node's "factory ID" (spec Section 4.5's 64-bit MAC), but reuses JOIN's uint16 fields — a 64-bit value doesn't fit. Resolved: `factory_id` is the low 16 bits of the node's real burned-in 802.15.4 MAC (see `pairing_mode.c`'s `get_factory_id`).
  - **Bench-only placeholders needing real hardware verification**: `BLINK_LED_GPIO` (pairing_mode.c) and `FACTORY_RESET_BUTTON_GPIO` (factory_reset_button.c, assumed to be the BOOT button's usual GPIO9) — same caveat status as M1's ADC GPIO0 note.
- ⬜ **Task 7 (bench test, not done)** — needs the full physical chain (M3) plus a factory-fresh node: place it near the dongle, confirm it appears on `/discover`, tap Blink and confirm the physical LED, name and claim it, confirm it starts reporting on the normal schedule via the main dashboard, hold the factory-reset button and confirm it reappears on `/discover`.
