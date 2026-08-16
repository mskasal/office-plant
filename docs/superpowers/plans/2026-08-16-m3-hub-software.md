# M3 Hub Software — Implementation Plan

**Goal:** The hub-radio dongle (root-role firmware from M2) forwards mesh traffic to a Raspberry Pi over USB/serial; the Pi runs a backend, SQLite storage, and a local dashboard showing plant identity + moisture status.

**Spec:** `docs/superpowers/specs/2026-08-16-office-plant-swarm-design.md` (Sections 3, 6). The spec says "USB/serial" but never pins down the actual wire protocol between dongle and Pi — that's decided here, since M3 and M4 both depend on it.

Lighter-weight plan: structure and decisions, not embedded source code — same rationale as M2.

## What M2 already provides

The root-role firmware (`firmware/main/root_main.c`) already receives mesh frames and knows how to transmit. M3 extends it to talk to a Pi instead of (or in addition to) logging to a human.

## Decision: dongle↔Pi serial protocol

Simple line-based, human-debuggable (readable in any serial terminal), no binary framing/checksum library — matches the spec's "start simple" ethos.

**Dongle → Pi**, one line per received mesh frame:
```
RX <hex-encoded protocol payload> <rssi>\n
```
Example: `RX 03010042640000000a -52\n` (a DATA frame, RSSI -52).

**Pi → Dongle**, one line per outbound command:
```
TX <hex-encoded protocol payload>\n
```
The dongle wraps whatever hex bytes it's given in the PHY length prefix (per M1's `ieee802154_radio_send` convention) and transmits. The dongle has no opinion about frame semantics — that's entirely the Pi's job, keeping the dongle firmware minimal and reusable for M4's new frame types without a dongle firmware change.

## Components

### Dongle firmware (`firmware/main/root_main.c`, extended)

- On `radio_on_receive_done`, in addition to (or instead of) logging, write `RX <hex> <rssi>\n` to UART.
- A UART read loop parsing incoming `TX <hex>\n` lines, decoding the hex, calling `ieee802154_radio_send`.

### Hub backend (`hub/`, new Python package)

- `hub/protocol_frame.py` — a Python port of `firmware/components/protocol/protocol_frame.c`'s exact byte layout (frame type, sender_id, per-type fields). This must stay byte-for-byte consistent with the C version; any change to one requires the same change in the other. Encode/decode functions mirror the C names: `decode_data_frame(buf) -> DataFrame`, etc. — same shapes as `sim/protocol.py`'s `DataFrame` from M0, since the wire format is a direct implementation of that same design.
- `hub/serial_bridge.py` — opens the dongle's serial port, reads `RX` lines, decodes them via `protocol_frame.py`, pushes decoded frames onto an internal queue/callback; sends `TX` lines when asked.
- `hub/models.py` — SQLite schema exactly as specified in spec Section 6:
  - `nodes(id, name, role, claimed_at, last_seen_at, battery_level)`
  - `readings(node_id, timestamp, moisture_status)`
- `hub/ingest.py` — on a decoded DATA frame from `serial_bridge`, upsert `nodes.last_seen_at`/`battery_level` and insert a `readings` row.
- `hub/api.py` — the web app (FastAPI per spec's tentative default — still not finalized, per the spec's own note; whoever implements M3 re-confirms this choice against the "efficiency" concern raised earlier before locking it in).
- `hub/dashboard/` — server-rendered page (Jinja2 per spec) listing every named node: last moisture status, battery, last-seen time, "offline" flag if `last_seen_at` is older than 2× the node's expected wake interval (spec Section 6).

## Task list

1. Extend `root_main.c` with the `RX`/`TX` serial framing described above.
2. `hub/protocol_frame.py` — Python port of the C frame format. At execution time, this should get the same host-testing treatment as the C version: round-trip encode/decode tests for each frame type, run with `pytest` (or plain asserts, matching M0's style), verified before moving on — this is a genuine correctness-critical piece (a mismatch between the C and Python byte layouts silently corrupts every reading) even though the rest of M3 is lighter-weight.
3. `hub/serial_bridge.py` + `hub/models.py` + `hub/ingest.py` — the ingestion pipeline. Testable with a fake serial port (feed canned `RX` lines, assert the SQLite rows that result) without needing real hardware.
4. `hub/api.py` + `hub/dashboard/` — the web app and page.
5. Bench test: M2's leaf node + a dongle running the extended `root_main.c` + a Pi (or dev machine) running `hub/`. Confirm the dashboard shows the leaf's real moisture reading and updates on each wake cycle.

## Verification

Tasks 2-3 (Python-only, no radio hardware needed) can be fully host-tested and should be, at execution time. Task 1 (dongle firmware) needs the ESP-IDF toolchain and hardware, same caveat as M1/M2. Task 5 needs the full physical chain (node + dongle + Pi).
