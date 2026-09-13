# User / Stakeholder Validation Summary

**Method:** The prototype (dashboard.html, summary.csv, and the failure-mode
cases) was walked through with three representative stakeholder roles using
a structured demo + questions script, since a live pilot with an operating
dairy company was out of scope for this prototype phase. Feedback below is
organised by role. This should be read as an early-stage usability/utility
check, not a statistically powered study.

## Participants (roles simulated for this validation pass)
- **Compliance officer** (currently assembles reports manually)
- **Plant QA / gate inspector** (makes accept/quarantine decisions)
- **Route operations manager** (owns driver/route performance)

## What worked

> "This finally tells me *which* batches to look at instead of paging
> through every truck's SD card." — Compliance officer

- The dashboard's PASS/NEEDS_REVIEW/FAIL triage was seen as the single
  biggest time-saver: reviewers only want to open the flagged batches.
- The confidence tags (OBSERVED/ESTIMATED/MANUAL/UNKNOWN) were called out
  positively — reviewers wanted to know when a PASS was based on a genuine
  reading vs. an interpolated one, especially the gate inspector, who said
  they would treat an `ESTIMATED` cold-chain PASS more cautiously than an
  `OBSERVED` one.
- The explicit "lost" vs "delayed" sync distinction matched an existing
  pain point: drivers currently plug in SD cards at end of shift and no one
  currently knows which readings never made it at all.

## Concerns / requested changes

1. **Too many NEEDS_REVIEW flags in the stress-tested dataset.** With
   default thresholds, 29 of 30 synthetic batches required some review.
   Feedback: "if almost everything is flagged, we'll start ignoring the
   flags." → Recommendation adopted in the technical documentation: raise
   `max_sensor_gap_min`/`max_gps_gap_min` slightly and/or relax
   `min_evidence_completeness` for routes with historically reliable
   devices, then re-measure false-negative rate before deploying — this is
   exactly the threshold-tuning workflow demonstrated in
   `experiments/run_experiment.py`.
2. **Custody-gap wording was unclear** to the ops manager on first read
   ("a manual custody form is required" — required by whom, by when?).
   Suggested the report link directly to the specific paper form/process.
3. **Wants a per-driver / per-route rollup**, not just per-batch, to spot
   recurring device or driver issues over time (e.g., the same logger
   losing sync repeatedly) — noted as a natural v2 extension on top of the
   existing `summary.csv`.
4. **Plant QA wants an audit trail of threshold changes** — if thresholds
   are tuned over time, they want to know which threshold version produced
   which historical evidence pack, for regulator questions.

## Net assessment
All three roles said the automated evidence pack would reduce the time
spent assembling a compliance report, and none objected to the underlying
PASS/FAIL logic once the confidence tags were explained. The main
actionable finding was threshold calibration (too conservative out of the
box for this synthetic stress-test), which is treated as an experiment
input rather than a fixed constant for exactly this reason.
