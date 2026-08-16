# M6 Hardware Finalization — BOM Decision Process

**Goal:** Lock the BOM for both node variants (sensor leaf vs. backbone), using real power/range numbers from M1-M5 — not estimates (spec Section 8).

**Spec:** `docs/superpowers/specs/2026-08-16-office-plant-swarm-design.md` (Section 3, 7).

Like M5, this milestone can't be filled in with real numbers today — solar/battery sizing depends on power draw M1 hasn't measured yet and placement M5 hasn't run yet. What's fixed here is the exact formula and decision process, so filling in the BOM later is arithmetic, not a fresh design exercise.

## Required inputs (produced by earlier milestones, not available yet)

- Measured deep-sleep current and measured active (sense+radio) current, and active-phase duration — from M1 Task 6's power-measurement procedure.
- Measured RF range/wall-penetration — from M2 Task 6's range test.
- Real placement data (how many backbone nodes were actually needed, and where) — from M5's output.

## Decision process

### Battery sizing
```
daily_energy_mWh = (sleep_current_mA × 24h × battery_voltage)
                  + (active_current_mA × active_duration_h × wakes_per_day × battery_voltage)

battery_capacity_mAh ≥ (daily_energy_mWh / battery_voltage) × days_of_autonomy
```
`days_of_autonomy` = **7 days**, fixed now as a documented default (covers a cloudy week without recharge) — this is a real decision, not a placeholder; it can be revisited later but shouldn't be left unset.

### Solar panel sizing
```
panel_mW_required ≥ daily_energy_mWh / (indoor_light_hours_per_day × derating_factor)
```
`derating_factor` = **0.10** as a starting conservative assumption for indoor ambient/window light versus a panel's outdoor-rated output — flagged explicitly as an assumption to be corrected against the real measured recharge rate once panels are on hand and placed at actual node locations (indoor light varies a lot by exact spot, which is exactly what M5's placement data captures).

### Enclosure requirements (fixed now, sourcing decided later)
- Fits within a typical plant pot's rim without interfering with the plant.
- Doesn't block the solar panel's light exposure.
- Lets the moisture probe reach soil while keeping the electronics dry.
- Exposes the factory-reset button (M4) without needing to open the enclosure.
- Total BOM cost per node stays within the spec's €10-15 target (Section 3) — if the real measured numbers push solar/battery sizing above that, that's a real finding to bring back to the user, not something to silently absorb.

### BOM table (structure fixed now, values filled in once inputs exist)

| Component | Sensor leaf | Backbone/relay |
|---|---|---|
| MCU module (ESP32-C6) | qty, part, cost | qty, part, cost |
| Moisture sensor | qty, part, cost | — (none) |
| Antenna/PA variant | standard | stronger, per M2's range findings |
| Battery | sized per formula above | sized per formula above, or mains-powered per spec Section 2 |
| Solar panel | sized per formula above | sized per formula above, or omitted if mains-powered |
| Enclosure | per requirements above | per requirements above |
| **Total per node** | sum | sum |

## Output

The filled-in BOM table above, plus a short note on whether the €10-15 target held or needed revisiting, becomes the input to sourcing/ordering hardware for M7's pilot deployment.
