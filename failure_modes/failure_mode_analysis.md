# Failure-Mode Analysis

Four hand-crafted single-route scenarios were built (`build_failure_cases.py`,
outputs in `cases/`) to isolate specific failure conditions and verify the
pipeline degrades gracefully rather than crashing, silently passing, or
silently discarding evidence. Results reproduced below.

## Case 1 — Total GPS loss
**Condition:** every GPS field blank for the whole route.
**Result:** `PASS` — the pipeline fell back to the driver-logged stop
coordinate in `route_events` and marked location evidence `ESTIMATED`
rather than failing outright or, worse, silently reporting `OBSERVED`.
**Why this matters:** rural collection routes routinely lose satellite fix
near valleys or inside covered collection points; a system that hard-fails
on any GPS gap would be unusable in the actual operating environment.

## Case 2 — Network outage (store-and-forward)
**Condition:** 6 of 10 readings arrive 5 hours late, 1 reading never syncs.
**Result:** `NEEDS_REVIEW`, correctly attributed to `data_sync_integrity`
(1 lost, 6 delayed-but-recovered) while every *other* check still passed
cleanly, because the recovered readings were used and correctly
time-ordered by `event_time` rather than arrival time.
**Why this matters:** this demonstrates the store-and-forward requirement
directly — evidence is not lost just because the network was down, and the
one genuinely lost reading is surfaced rather than swept under a "no data =
fine" assumption.

## Case 3 — Total sensor failure
**Condition:** the temperature probe dies after the 3rd reading and never
recovers for the rest of the route — a genuine, unfillable gap (no
neighbouring real value exists to interpolate the tail from).
**Result:** `NEEDS_REVIEW`, correctly distinguished from the interpolatable
mid-series-gap case: the message explicitly says the tail is unrecoverable,
rather than mislabelling it as "a big interpolation gap" (an earlier bug in
this prototype conflated the two — see Error Analysis below).
**Why this matters:** an evidence system must be honest about the
difference between "we patched around a small gap" and "we genuinely do
not know what happened for the back half of the route" — these carry very
different audit risk.

## Case 4 — Combined worst case
**Condition:** patchy GPS, patchy sensor, delayed network sync, ONE
isolated noise spike, and a real 5-reading sustained cold-chain excursion,
all in the same 14-ping route.
**Result:** `FAIL` on cold chain, correctly identifying a 30-minute
sustained excursion, while separately reporting the noise spike as
rejected and the GPS/network gaps as bridged/flagged on their own checks.
**Why this matters:** this is the scenario that most resembles a bad day in
the field, and it's the one that most needs the system to work — a naive
global-statistics filter would have hidden the real excursion.

## Error analysis: a bug this exercise actually caught

Building Case 4 surfaced a real defect during development: the first
version of the noise filter used a single **global** median/MAD across the
whole route. Under that version, five consecutive elevated readings (the
genuine excursion) pulled the global median enough that the filter's
z-score classified the *entire elevated run* as "noise" and rejected it —
the excursion was invisible, exactly the failure mode this system is meant
to prevent.

Fix: switched to a **local rolling-window** median/MAD (window=5, centred
on each point). A real excursion's own points lie inside their own window,
so the window's median moves with it and the excursion is *not* penalized;
an isolated one-off spike stays surrounded by calm neighbours in its
window and *is* correctly rejected. After the fix, Case 4 correctly
returns `FAIL` with the excursion intact and the spike separately removed
— see `experiments/results.csv` for the corresponding measured precision/
recall improvement (excursion detection F1 rose from 90% to 100% on the
30-batch dataset after this fix, with zero remaining false negatives).

## Summary table

| Case | Overall status | Key fallback demonstrated |
|---|---|---|
| Total GPS loss | PASS | Route-event coordinate fallback |
| Network outage | NEEDS_REVIEW | Store-and-forward recovery + lost-record disclosure |
| Total sensor failure | NEEDS_REVIEW | Honest "unrecoverable gap" vs. "patched gap" distinction |
| Combined worst case | FAIL | Real signal preserved despite simultaneous noise/gaps |
