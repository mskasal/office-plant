# M2 Two-Node Link — Implementation Plan

**Goal:** Two physical ESP32-C6 nodes exchange BEACON/JOIN/DATA over real 802.15.4 radio, validating the M0 protocol logic (hop-count-first/RSSI-tiebreak parent selection) against real RF — including range and one-wall penetration.

**Spec:** `docs/superpowers/specs/2026-08-16-office-plant-swarm-design.md` (Section 4), `docs/superpowers/plans/2026-08-16-m0-protocol-simulation.md` (parent-selection logic being ported to C), `docs/superpowers/plans/2026-08-16-m1-single-node-firmware.md` (radio/sensor/sleep modules being reused).

This is a lighter-weight plan: architecture, structure, and the decisions that need pinning down now — not embedded source code. Real implementation happens at execution time, following the same TDD/verification discipline M0 and M1 used (host-test what's hardware-independent, flash-and-observe what isn't).

## What M1 already provides

`firmware/components/protocol` (frame format) and `firmware/main/ieee802154_radio.*` (send **and** receive — M1's `main.c` just never called receive) are reused as-is. Nothing in M1 needs to change.

## What's new

### 1. Pure parent-selection logic, ported to C

Mirrors `sim/protocol.py`'s `select_parent` exactly (same rule: lowest hop-count wins, RSSI breaks ties), so it's host-testable with `gcc` the same way M1 Task 1 was — this is the one piece of M2 that should still get the full TDD treatment at execution time (write the C port, write host tests mirroring M0's `test_protocol_parent_selection.py` cases, compile+run with `gcc`, verify, commit).

- New component: `firmware/components/mesh/` (hardware-independent, like `protocol`)
- Interface (the decision, not the implementation):
  ```c
  typedef struct {
      uint16_t sender_id;
      uint8_t hop_count;
      int8_t rssi;
  } parent_candidate_t;

  /* Returns sender_id of the best candidate, or -1 if candidates is empty. */
  int select_parent(const parent_candidate_t *candidates, size_t count);
  ```

### 2. Role selection: root vs leaf

M2 has exactly two boards. One acts as hop-count-0 root (previewing M3's hub-radio dongle role), the other as a leaf. **Decision:** a CMake cache variable, not a runtime GPIO strap — simplest thing that works for a two-board bench test:

```
idf.py build -DNODE_IS_ROOT=1   # root board
idf.py build -DNODE_IS_ROOT=0   # leaf board (default if omitted)
```

`firmware/main/main.c` reads this via a `CONFIG`-style compile definition and branches to one of two entry behaviors described below. (M5's real multi-node deployment replaces this bench-only mechanism with real addressing from M4's provisioning — this hardcoded flag is scoped to M2's two-board test only.)

### 3. Root-role behavior (`firmware/main/root_main.c`)

Radio stays powered continuously (no deep-sleep cycling — matches how the real M3 hub-radio dongle behaves, since it's not battery-constrained). Periodically transmits a BEACON (`hop_count=0`), listens continuously for JOIN and DATA frames, logs every received frame (sender, type, RSSI) over UART. This is a direct preview of M3's dongle firmware minus the serial forwarding to a Pi.

### 4. Leaf-role behavior (extends M1's wake cycle)

Same wake → sense → sleep shape as M1, with a discovery step inserted before sending:
1. Wake, log boot (M1's `sleep_wake_log_boot`).
2. Listen briefly (bounded timeout, e.g. 2s) for BEACON frames via `ieee802154_radio_receive`, collecting `parent_candidate_t` entries.
3. Call `select_parent`; if none heard, skip this cycle (log "no parent found", sleep, retry next wake — this is the real behavior an isolated node will show, not an error case to special-case away).
4. Send a JOIN frame (M1's existing `join_frame_t`/`encode_join_frame`) to the selected parent.
5. Read moisture (M1's `moisture_sensor_read_raw`), send DATA frame (M1's existing `encode_data_frame`).
6. Sleep (M1's `sleep_wake_go_to_sleep`).

With only two boards, the leaf's parent is always the root directly (hop_count becomes 1) — multi-hop chains aren't exercised until M5.

## Task list

1. Port `select_parent` to C in `firmware/components/mesh/`, host-tested with `gcc` (same rigor as M1 Task 1) — full test cases to write at execution time, mirroring `tests/test_protocol_parent_selection.py`'s three cases (empty list, lowest hop-count wins, RSSI tiebreak).
2. Implement `root_main.c` (continuous beacon + receive + UART log).
3. Extend `main.c` with the leaf-role discovery step (steps 2-3 above), reusing M1's existing sense/send/sleep code for steps 5-6.
4. Wire the `NODE_IS_ROOT` build flag into `firmware/main/CMakeLists.txt` and `main.c`'s entry dispatch.
5. Bench test: flash root to board A, leaf to board B, same room. Confirm the leaf's log shows a discovered parent, a sent JOIN, a sent DATA, and the root's log shows the corresponding received frames with a real RSSI value.
6. Range/wall test: separate the boards by increasing distance, then by one interior wall, repeating the bench test. Record the point where the link starts failing — this is the real-world input M5 (relay placement) and M6 (whether backbone nodes need external antennas) both need, and can't be fabricated ahead of the actual radios existing.

## Verification

Task 1 is host-testable and should be actually run (`gcc` compile + execute), same as M0 and M1 Task 1. Tasks 2-6 require the ESP-IDF toolchain and two physical ESP32-C6 boards — not available in this authoring environment, same caveat as M1 Tasks 2-6.

### Implementation status (as of this commit)

- ✅ **Task 1** — `firmware/components/mesh/mesh_parent_select.{h,c}` implemented and host-tested with `gcc`: all 3 checks pass (mirrors `tests/test_protocol_parent_selection.py`'s three cases exactly).
- ✅ **Tasks 2-4** — code written: `firmware/main/root_main.c` (continuous beacon + receive + log), `firmware/main/leaf_main.c` (M1's wake cycle extended with the discovery/select_parent/JOIN step), `main.c`'s `NODE_IS_ROOT`-based dispatch, and `firmware/main/CMakeLists.txt` wiring the build flag through `target_compile_definitions`. Along the way, fixed a real bug inherited from M1: `CMakeLists.txt`'s `SRCS` only ever listed `main.c`, so `sleep_wake.c`/`moisture_sensor.c`/`ieee802154_radio.c` were never compiled — a real `idf.py build` would have failed with undefined-reference errors. All firmware sources are now listed.
- ⬜ **Tasks 5-6 (not done)** — the bench test (flash root to board A, leaf to board B, confirm the log sequence) and the range/wall test both require two physical ESP32-C6 boards and ESP-IDF, neither available in this environment. Whoever has the hardware next should run `idf.py build -DNODE_IS_ROOT=1` for board A, `idf.py build -DNODE_IS_ROOT=0` (or omitted) for board B, and follow Task list items 5-6 above.
