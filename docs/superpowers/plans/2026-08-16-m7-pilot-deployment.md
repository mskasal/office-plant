# M7 Pilot Deployment — Rollout Process

**Goal:** Deploy across the real office (target 30 nodes), run for at least two weeks, tune schedule/thresholds, identify dead zones — the real-world acceptance test for v1 (spec Section 8, 9).

**Spec:** `docs/superpowers/specs/2026-08-16-office-plant-swarm-design.md` (Section 9).

## Prerequisites

M1-M6 complete: firmware, hub software, provisioning, multi-hop validated at moderate scale (M5), and a finalized BOM (M6) with hardware actually built/ordered to that BOM.

## Process

### Pre-deployment checklist
- All 30 nodes assembled to the M6 BOM and flashed with production firmware — critically, using the **production wake interval** (spec default ~2x/day), not M1's 30-second test interval left over from bench testing.
- Hub (Pi + dongle) running continuously in its permanent location.

### Week 1
- Provision every node via M4's discover/tap/blink/name flow, placing each in its real plant's pot as it's provisioned.
- Check the dashboard daily. Any node that never appears, or goes offline, gets physically investigated (moved closer to a neighbor, or a backbone node added) same day if possible.

### Week 2
- Continue daily monitoring with week 1's issues already addressed.
- At least twice during the week, physically check a sample of plants against what the dashboard claims (ground truth spot-check) — this is the only way to catch a systematic moisture-threshold miscalibration that wouldn't show up as an "offline" node.

### Success criteria
- Zero missed waterings attributable to the system across the two weeks (i.e., no plant went unwatered because the dashboard failed to flag it, or flagged it too late).
- The user trusts the dashboard enough to stop physically checking plants that show as "fine" — this is inherently a qualitative judgment call for the user to make at the end of the two weeks, not a number this plan can fix in advance.

## Output

A short retro: which nodes (if any) needed repositioning or a nearby backbone node, whether the moisture threshold (first set as a placeholder in M1 Task 6) needed recalibrating, and whether v1 is considered done or needs another iteration before being called finished.
