# Technical Documentation — Dairy Compliance Evidence Pack Prototype

## 1. Purpose
Automate the assembly of an audit-ready **compliance evidence pack per milk
batch**, joining five disconnected data sources, while remaining usable
when GPS, network, or sensor data is incomplete or noisy.

## 2. Architecture

```
data_generation/generate_data.py   -> data/*.csv  (synthetic field data + ground_truth.csv)
app/evidence_pack.py               -> core engine: cleaning, fallback, checks, scoring
app/cli.py                         -> functional application: runs pipeline, writes reports
experiments/run_experiment.py      -> baseline vs automated measurement, threshold tuning
failure_modes/build_failure_cases.py -> hand-crafted edge cases + fallback demonstration
```

No server or database is required; everything runs as plain Python (stdlib
only for the engine) over CSV files, so it can run on a laptop in the field
or be dropped into an existing batch job.

## 3. Data model (five sources, joined by `route_id` / `device_id` / `batch_id`)

| File | Grain | Key fields |
|---|---|---|
| `sensor_logs.csv` | one ping | `device_id, route_id, event_time, sync_time, sync_status, temperature_c, latitude, longitude` |
| `calibration.csv` | one device | `device_id, last_calibration_date, calibration_interval_days, calibration_offset_c, next_due_date` |
| `handovers.csv` | one custody transfer | `handover_id, route_id, stage, from_party, to_party, quantity_l, event_time, signature_captured` |
| `route_events.csv` | one planned stop | `route_id, stop_seq, producer_id, planned_time, actual_arrival_time, status, latitude, longitude` |
| `batches.csv` | one product batch | `batch_id, route_id, device_id, formed_time, total_volume_l, producer_ids, quality_test_result` |

`sync_status` (`live` / `delayed` / `lost`) is the store-and-forward marker:
every record carries the time it actually happened (`event_time`) separately
from when it reached the server (`sync_time`), which is what makes ordering
and gap analysis correct even when data arrives out of order or very late.

## 4. Missing/noisy data handling strategy

| Problem | Strategy | Confidence tag on output |
|---|---|---|
| A single/short run of missing sensor readings | Linear interpolation between the nearest real readings before/after the gap | `ESTIMATED` |
| Missing readings at the very start/end of a route (no neighbour to interpolate from) | Left as an explicit, reported gap — **never silently dropped or silently assumed safe** | `UNKNOWN` |
| Noisy/spiky sensor readings | **Local rolling-window median/MAD despiking** (window=5, centred), not a single global statistic. A genuine sustained excursion pulls its own local window up with it and is *not* flagged as noise, whereas an isolated one-off spike stands out from calm neighbours and *is* rejected. This distinguishes “real event” from “sensor glitch” — a single global threshold cannot. | `OBSERVED` after despiking |
| Missing GPS | Fall back to the lower-frequency, driver-logged stop coordinates in `route_events` | `ESTIMATED` |
| No GPS and no fallback source | Reported as `NEEDS_REVIEW`, not silently passed | `UNKNOWN` |
| Network outage (store-and-forward) | All logic operates on `event_time`; delayed records are recovered and used once they land, and are reported in the `data_sync_integrity` check | `MIXED` |
| Data that never syncs at all | Explicitly counted and surfaced as `lost` — this is the one case the system genuinely cannot fix, and it says so instead of hiding it | flagged in `data_sync_integrity` |
| Broken custody link (no signature/timestamp) | Reported as needing a manual paper fallback form, not silently treated as compliant | `MANUAL` |

## 5. Checks performed per batch

1. **Cold chain** — sustained excursions above `cold_chain_limit_c` for at
   least `excursion_min_duration_min`, computed on the despiked +
   interpolated series.
2. **Location traceability** — GPS coverage continuity, with route-event
   fallback.
3. **Calibration validity** — device calibration due date vs. the batch's
   formation time.
4. **Custody chain** — every handover has a captured timestamp/signature.
5. **Route completion** — every planned stop was actually completed.
6. **Data sync integrity** — how much evidence arrived late or never
   arrived (store-and-forward health), reported as its own check so gaps
   are visible rather than folded silently into the other checks.

Each check returns `PASS / FAIL / NEEDS_REVIEW / INSUFFICIENT_DATA` plus a
confidence tag. The **overall batch status** is the worst of the six check
statuses; if fewer than `min_evidence_completeness` (default 60%) of checks
have real/estimated evidence behind them, a would-be PASS is downgraded to
`NEEDS_REVIEW` — the system will not certify a batch it doesn't actually
have enough evidence about.

## 6. Tunable thresholds (`ThresholdConfig`)

| Parameter | Default | Effect of raising it |
|---|---|---|
| `cold_chain_limit_c` | 6.0°C | Fewer excursion flags, more risk tolerance |
| `excursion_min_duration_min` | 10 min | Fewer flags on brief/transient blips, more risk of missing short real events |
| `noise_spike_zscore` | 3.0 | Higher = less aggressive despiking (more noise kept as "real") |
| `max_sensor_gap_min` / `max_gps_gap_min` | 20 min | Higher = more tolerant of patchy telemetry before flagging for review |
| `min_evidence_completeness` | 0.6 | Higher = stricter about certifying batches with partial evidence |

These are exposed as CLI flags on `app/cli.py` and are grid-searched in
`experiments/run_experiment.py` against ground truth.

## 7. Known limitations
- Synthetic data approximates real fleet telemetry but does not capture
  every real-world failure mode (e.g. clock drift between devices,
  multi-day routes, partial batch splits/re-merges).
- The despiking filter assumes readings are roughly evenly spaced; very
  irregular sampling would need window sizing in time rather than count.
- Calibration and custody checks are currently point-in-time (batch
  formation time) rather than continuous coverage across the whole
  collection window — a device could in principle expire *during* a route.
- The prototype does not yet model multi-day / multi-plant merges of the
  same batch, or reconciling volumes against producer-side records.

## 8. How to run

```bash
cd data_generation && python3 generate_data.py --seed 42 --out ../data
cd ../app && python3 cli.py --data ../data --out ../outputs
cd ../experiments && python3 run_experiment.py --data ../data --out results.csv
cd ../failure_modes && python3 build_failure_cases.py
```
