# M5 Multi-Hop Mesh at Scale — Validation Process

**Goal:** Validate multi-hop routing, self-healing (on node move/power-loss), and hub-governed config push at real physical scale across multiple rooms (spec Section 8).

**Spec:** `docs/superpowers/specs/2026-08-16-office-plant-swarm-design.md` (Sections 4, 7).

This milestone is inherently data-driven — node/room placement, wall attenuation, and how many backbone nodes are actually needed depend on the real office layout and the real range numbers M2 measures. There is nothing to pre-decide here beyond process and success criteria; fabricating placement numbers now would be worse than leaving them for execution time.

## Prerequisites

M1-M4 complete: node firmware (sense/sleep/radio/provisioning) and hub software (dongle + Pi + dashboard) all working end to end for at least one node, per M2-M4's bench tests.

## Process

1. **Build enough nodes.** Using M1-M4's firmware, assemble several sensor-leaf nodes and at least one backbone/relay node (bare — no sensor, same firmware). Exact count is whatever's practical to build before this milestone; doesn't need to be the full 30 yet (that's M7).
2. **Deploy across real rooms.** Walk the actual office, note where glass doors/thin walls sit relative to where the hub will live, and place nodes accordingly. Use M2's measured range/wall-penetration result to decide where a backbone node is likely needed versus where a direct or one-hop link should suffice. This placement is a judgment call made on-site, not something a document can specify in advance.
3. **Run the validation checklist** (mirrors what M0's simulation already validated in software — this milestone is checking the same properties hold on real hardware):
   - Every deployed, provisioned node's data reaches the hub within its wake cycle.
   - Power off (or physically remove) a relay node that other nodes depend on; confirm dependents either reroute through an alternate path within their next wake cycle, or show "offline" on the dashboard if genuinely cut off (per spec Section 6) — either outcome is correct behavior, not a failure, as long as it's one of the two.
   - Physically move a node; confirm it re-parents (hop count / dashboard-visible route changes) within its next wake cycle, with no manual resync step.
   - Push a config change from the hub (e.g., a different wake interval); confirm a node picks it up on its next check-in (spec Section 4.1's "hub is in charge, but only ever speaks during a window a node itself opened").
4. **Success criteria:** at least 90% of deployed nodes report successfully across a continuous 48-hour observation window. Any node below that gets a backbone node added nearby and is retested — this threshold is a real, fixed acceptance bar (not a placeholder), chosen to allow for a small number of genuinely awkward locations without treating the whole milestone as blocked by one outlier.

## Output

A short written record (can be an update to this file, or a new dated note) of: how many nodes were deployed, where backbone nodes ended up being necessary, and whether the 90% bar was met. This record is the direct input to M6 (which needs real range/placement data) and M7 (which needs to know the mesh already works at moderate scale before committing to the full 30-node office rollout).

### Implementation status (as of this commit)

M5 itself has no code deliverable — it's a physical deployment/validation process (Process steps 1-4 above: build nodes, walk the real office, run the checklist against real hardware over a 48-hour window). None of that has been done here; it requires real nodes, a real office, and time this environment doesn't have. **The Output section above is still unwritten — nothing has been fabricated in its place.**

What was done instead: while reading this plan's validation checklist item 4 ("push a config change from the hub... confirm a node picks it up on its next check-in"), found that the mechanism it depends on didn't exist. Spec Section 4.1 commits to hub-governed config push as core v1 protocol behavior, but nothing through M4 implemented a frame or firmware/hub code for it — so checklist item 4 wasn't actually runnable. Closed that gap:

- ✅ **`FRAME_TYPE_CONFIG`** (protocol_frame.h/.c, hub/protocol_frame.py) — hub → node, piggybacked on a DATA response window, carries `wake_interval_sec` + `moisture_dry_threshold_raw`, targeted by `target_node_id`. Host-tested (16 C checks, 12 pytest cases, all passing).
- ✅ **`hub/node_config.py`** — operator-set desired config per node (`node_config` table, new — spec Section 6's schema never accounted for where this state lives, another real gap), `maybe_push_config` sends it back on that node's next DATA frame. Host-tested (6 cases).
- ✅ **Dashboard action** — `/nodes/{id}/config` lets an operator actually push a change from the running hub, which is what checklist item 4 needs to be testable at all. Also fixed the dashboard's offline-threshold math to use each node's real configured interval instead of always assuming the M1/M2 bench default.
- ⚠️ **`firmware/main/node_config.c/h`**, wired into `leaf_main.c` (listens for a targeted CONFIG frame after sending DATA, applies and persists it via NVS, re-reads the interval before sleeping so a just-pushed config takes effect immediately) — written against real ESP-IDF NVS APIs but not run through `idf.py build`, same constraint as every firmware change since M1.

**None of the actual M5 process (build nodes, deploy, 48-hour observation, backbone placement, the 90% success bar) has been attempted.** That's real-world work for whoever has the hardware and office — this commit only makes sure the config-push half of the validation checklist has something to actually test once that happens.
