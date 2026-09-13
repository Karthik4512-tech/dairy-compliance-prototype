# Dairy Compliance Evidence Pack — Field-Ready Prototype

An automated compliance evidence pack for a dairy company collecting milk
from many small producers. It joins **sensor logs, calibration records,
custody handovers, route events, and product batches** into one audit-ready
report per batch — and stays usable when GPS, network, or sensor data is
incomplete, exactly the condition that makes today's manual, disconnected
process slow and inconsistent.

This is a working prototype, not a slide-only concept: it includes a real
data pipeline, a functional application, a measurable experiment against
ground truth, four verified failure-mode cases, a simulated stakeholder
validation pass, and full technical documentation.

## Project layout

```
data_generation/generate_data.py   Synthetic field data generator (5 sources + ground truth)
data/                              Generated CSVs (sensor_logs, calibration, handovers,
                                   route_events, batches, ground_truth)
app/evidence_pack.py               Core engine: joins sources, cleans/interpolates data,
                                   applies tunable compliance checks
app/cli.py                         Functional application: runs the pipeline, writes reports
outputs/                           evidence_packs.json, summary.csv, dashboard.html
experiments/run_experiment.py      Baseline vs automated measurement + threshold tuning
experiments/results.csv            Measured precision/recall/F1 per detector
failure_modes/build_failure_cases.py   Four hand-crafted edge cases
failure_modes/cases/               Per-case markdown output
failure_modes/failure_mode_analysis.md Write-up, including a real bug found + fixed
docs/field_workflow_map.md         Current (manual) vs new (automated) workflow
docs/technical_documentation.md    Architecture, data schemas, thresholds, limitations
docs/user_feedback_summary.md      Simulated stakeholder validation
presentation/                      Short slide deck (.pptx) + build script
```

## Quick start

```bash
# 1. Generate a synthetic operating day (30 routes/batches)
cd data_generation && python3 generate_data.py --seed 42 --out ../data

# 2. Run the functional application (produces the audit dashboard)
cd ../app && python3 cli.py --data ../data --out ../outputs
#   -> open ../outputs/dashboard.html in a browser

# 3. Run the measurable experiment (baseline vs automated, threshold tuning)
cd ../experiments && python3 run_experiment.py --data ../data --out results.csv

# 4. Run the failure-mode / edge-case demonstrations
cd ../failure_modes && python3 build_failure_cases.py
```

No external dependencies are required for the engine or CLI (Python
standard library only). The presentation deck was built with `pptxgenjs`
(Node.js).

## Headline results (30-batch synthetic day, see `experiments/results.csv`)

| Detector | Baseline (manual-style) | Automated (default) | Automated (tuned) |
|---|---|---|---|
| Cold-chain excursion | 65% precision / 100% recall (F1 79%) | **100% / 100% (F1 100%)** | **100% / 100% (F1 100%)** |
| Custody gap | 100% / 100% | 100% / 100% | 100% / 100% |
| Missed stop | 100% / 100% | 100% / 100% | 100% / 100% |
| Calibration expired | 100% / 100% | 100% / 100% | 100% / 100% |

The automated pipeline reaches 100% precision and 100% recall across all detectors out of the box using the local rolling-window filter and graceful degradation logic (described in `failure_modes/failure_mode_analysis.md`). Tuned thresholds provide configurable sensitivity margins.

**Effort:** ~22 min/batch of manual assembly (660 min / 11.0 hrs for 30
batches) vs. the automated pipeline running in milliseconds plus ~4 min of
human review per **flagged** batch only — an estimated **82% reduction**
in compliance-report assembly effort for this dataset.

**Robustness:** all four crafted failure cases (total GPS loss, network
outage/store-and-forward, total sensor failure, and a combined worst case
with a real excursion hidden in noise and gaps) produced correct,
explainable outcomes rather than crashes, silent passes, or silently
dropped evidence — see `failure_modes/failure_mode_analysis.md`.

## Design principle
Every check degrades gracefully and is labelled with a confidence tag
(`OBSERVED` / `ESTIMATED` / `MANUAL` / `UNKNOWN`) rather than either
blocking on missing data or silently treating a gap as compliant. See
`docs/technical_documentation.md` §4 for the full missing/noisy-data
handling table, and `docs/field_workflow_map.md` for where store-and-
forward and manual fallback sit in the actual field workflow.
