"""
Compliance Evidence Pack Engine
================================
Joins sensor logs, calibration records, custody handovers, route events and
product batches into one per-batch compliance evidence pack, WITHOUT
requiring complete GPS/network/sensor coverage.

Design principles (see docs/technical_documentation.md for full rationale):

1. Never block on missing data. Every check degrades gracefully to a
   documented fallback and is labelled with a confidence tag:
   OBSERVED  -> a real reading was available
   ESTIMATED -> interpolated/derived from neighbouring readings
   MANUAL    -> no device evidence exists; a manual/paper fallback record
               would be required (flagged for human entry in a real deployment)
   UNKNOWN   -> no evidence and no fallback possible -> explicit gap, reported
               as such rather than silently dropped or silently passed.

2. Store-and-forward is native: every record carries an `event_time` (when
   it actually happened) and a `sync_time`/`sync_status` (when it reached
   the server). All correctness logic is computed on `event_time`; sync
   metadata is only used to flag delayed evidence and to explain gaps.

3. Thresholds are configurable (see ThresholdConfig) so they can be tuned
   against measured false-positive/false-negative rates (experiments/).
"""
from __future__ import annotations
import csv
import os
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional


def _parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


# --------------------------------------------------------------------------
# Tunable thresholds
# --------------------------------------------------------------------------
@dataclass
class ThresholdConfig:
    cold_chain_limit_c: float = 6.0          # regulatory temperature ceiling
    excursion_min_duration_min: int = 10     # must persist this long to count as a real excursion
    noise_spike_zscore: float = 3.0          # readings beyond this many MADs from local median = noise
    calibration_grace_days: int = 0          # days past due date still tolerated
    max_gps_gap_min: int = 20                # gap above which location coverage is "insufficient"
    max_sensor_gap_min: int = 20             # gap above which temperature coverage is "insufficient"
    min_evidence_completeness: float = 0.6   # fraction of checks needing real/estimated evidence to auto-pass
    custody_gap_is_blocking: bool = True      # a broken custody link forces NEEDS_REVIEW


@dataclass
class CheckResult:
    name: str
    status: str            # PASS | FAIL | NEEDS_REVIEW | INSUFFICIENT_DATA
    confidence: str        # OBSERVED | ESTIMATED | MANUAL | UNKNOWN | MIXED
    detail: str
    evidence_refs: list = field(default_factory=list)


@dataclass
class EvidencePack:
    batch_id: str
    route_id: str
    checks: list
    overall_status: str
    completeness_score: float
    generated_at: str


def _median(values):
    return statistics.median(values) if values else None


def _mad(values, med):
    if not values:
        return 0.0
    return statistics.median([abs(v - med) for v in values])


def clean_sensor_series(pings, thresholds: ThresholdConfig, window=5):
    """
    Denoise a chronological list of {event_time, temperature_c} dicts using a
    LOCAL rolling median/MAD (not a single global one).

    Why local, not global: a genuine sustained cold-chain excursion (several
    consecutive elevated readings) and a single isolated sensor noise spike
    can look equally "extreme" against a global median if the rest of the
    route is calm. A rolling window centred on each point lets a real,
    multi-point excursion pull its own local median up with it (so it is
    NOT flagged), while a one-off spike stays isolated against neighbours on
    both sides that remain at baseline (so it IS flagged). This is the same
    reason production despiking filters use a moving-window median rather
    than a single dataset-wide statistic.

    Returns (cleaned_list, stats) where each item gains a `flag` of
    OBSERVED / NOISE_REJECTED / MISSING.
    """
    real_idx = []
    real_vals = []
    for i, p in enumerate(pings):
        raw = p.get("temperature_c") if isinstance(p, dict) else None
        if raw not in (None, ""):
            try:
                real_vals.append(float(raw))
                real_idx.append(i)
            except (ValueError, TypeError):
                pass

    half = window // 2

    noise_mask = {}
    for pos, i in enumerate(real_idx):
        lo, hi = max(0, pos - half), min(len(real_vals), pos + half + 1)
        win = real_vals[lo:hi]
        med = _median(win)
        mad = _mad(win, med)
        # On a flat baseline (mad == 0 or tiny), use an effective scale floor (0.25°C)
        # so that wild spikes (e.g. 25°C spike on 4°C baseline) are identified as noise
        # without flagging normal readings or dividing by zero.
        scale = max(mad, 0.25)
        v = real_vals[pos]
        z = abs(v - med) / scale if scale else 0.0
        noise_mask[i] = med is not None and z > thresholds.noise_spike_zscore

    cleaned = []
    n_missing, n_noise = 0, 0
    for i, p in enumerate(pings):
        raw = p.get("temperature_c") if isinstance(p, dict) else None
        if raw in (None, ""):
            cleaned.append({**p, "temperature_c": None, "flag": "MISSING"})
            n_missing += 1
            continue
        try:
            v = float(raw)
        except (ValueError, TypeError):
            cleaned.append({**p, "temperature_c": None, "flag": "MISSING", "error": "MALFORMED"})
            n_missing += 1
            continue
        if noise_mask.get(i):
            cleaned.append({**p, "temperature_c": None, "raw_value": v, "flag": "NOISE_REJECTED"})
            n_noise += 1
        else:
            cleaned.append({**p, "temperature_c": v, "flag": "OBSERVED"})
    return cleaned, {"n_missing": n_missing, "n_noise_rejected": n_noise, "n_total": len(pings)}


def interpolate_gaps(cleaned, field_name="temperature_c"):
    """Linear interpolation across MISSING/NOISE_REJECTED points bounded by
    real neighbours; leading/trailing gaps stay unresolved (UNKNOWN)."""
    n = len(cleaned)
    out = [dict(c) for c in cleaned]
    i = 0
    while i < n:
        if out[i].get(field_name) is not None:
            i += 1
            continue
        j = i
        while j < n and out[j].get(field_name) is None:
            j += 1
        # gap is (i .. j-1); need real values at i-1 and j
        if i > 0 and j < n:
            t0 = _parse_dt(out[i - 1].get("event_time"))
            t1 = _parse_dt(out[j].get("event_time"))
            v0 = out[i - 1].get(field_name)
            v1 = out[j].get(field_name)
            if t0 is not None and t1 is not None and v0 is not None and v1 is not None:
                span = (t1 - t0).total_seconds() or 1
                for k in range(i, j):
                    tk = _parse_dt(out[k].get("event_time"))
                    if tk is not None:
                        frac = (tk - t0).total_seconds() / span
                        out[k][field_name] = round(v0 + frac * (v1 - v0), 2)
                        out[k]["flag"] = "ESTIMATED"
                    else:
                        out[k]["flag"] = "UNKNOWN"
            else:
                for k in range(i, j):
                    out[k]["flag"] = "UNKNOWN"
        else:
            for k in range(i, j):
                out[k]["flag"] = "UNKNOWN"
        i = j
    return out


def max_gap_minutes(pings, has_value_key):
    """Largest time gap (minutes) between consecutive pings that DO carry a value."""
    times = []
    for p in pings:
        if p.get(has_value_key) not in (None, ""):
            t = _parse_dt(p.get("event_time"))
            if t is not None:
                times.append(t)
    times.sort()
    if len(times) < 2:
        return None
    return max((b - a).total_seconds() / 60 for a, b in zip(times, times[1:]))


# --------------------------------------------------------------------------
# Individual compliance checks
# --------------------------------------------------------------------------

def check_cold_chain(route_pings, thresholds: ThresholdConfig) -> CheckResult:
    if not route_pings:
        return CheckResult("cold_chain", "INSUFFICIENT_DATA", "UNKNOWN",
                            "No temperature telemetry exists for this route at all.")
    cleaned, stats = clean_sensor_series(route_pings, thresholds)
    filled = interpolate_gaps(cleaned)
    gap = max_gap_minutes(route_pings, "temperature_c")
    coverage_ok = gap is None or gap <= thresholds.max_sensor_gap_min

    # find sustained excursions on the filled (observed+estimated) series
    excursion_runs = []
    run_start = None
    for idx, p in enumerate(filled):
        v = p.get("temperature_c")
        over = v is not None and v > thresholds.cold_chain_limit_c
        if over and run_start is None:
            run_start = idx
        is_last = (idx == len(filled) - 1)
        if (not over or is_last) and run_start is not None:
            last_over = idx if (is_last and over) else idx - 1
            t0 = _parse_dt(filled[run_start].get("event_time"))
            t1 = _parse_dt(filled[last_over].get("event_time"))
            if t0 and t1:
                dur = (t1 - t0).total_seconds() / 60
                if dur >= thresholds.excursion_min_duration_min:
                    excursion_runs.append((run_start, last_over, dur))
            run_start = None

    unknown_points = sum(1 for p in filled if p.get("flag") == "UNKNOWN")
    confidence = "OBSERVED"
    if any(p.get("flag") == "ESTIMATED" for p in filled):
        confidence = "ESTIMATED" if confidence == "OBSERVED" else confidence
    if unknown_points:
        confidence = "MIXED" if confidence != "UNKNOWN" else "UNKNOWN"

    n_real = stats["n_total"] - stats["n_missing"] - stats["n_noise_rejected"]
    evidence_refs = [f"{n_real}/{stats['n_total']} readings observed",
                     f"{stats['n_noise_rejected']} noise spikes rejected",
                     f"{unknown_points} points with no evidence and no fallback"]

    if excursion_runs:
        detail = (f"Sustained cold-chain excursion above {thresholds.cold_chain_limit_c}C for "
                  f"{max(r[2] for r in excursion_runs):.0f} min (threshold {thresholds.excursion_min_duration_min} min).")
        return CheckResult("cold_chain", "FAIL", confidence, detail, evidence_refs)

    if unknown_points > 0:
        detail = (f"{unknown_points} reading(s) at the start/end of the route have no temperature evidence "
                  f"and no neighbouring value to interpolate from (sensor failed and never recovered, or "
                  f"failed before the first reading) - a genuine, unfillable gap. No excursion detected in "
                  f"the data that IS available, but coverage cannot be confirmed complete.")
        return CheckResult("cold_chain", "NEEDS_REVIEW", confidence, detail, evidence_refs)

    if not coverage_ok:
        detail = (f"Temperature coverage gap of {gap:.0f} min exceeds {thresholds.max_sensor_gap_min} min "
                  f"tolerance; missing points were interpolated but the sparsity itself is flagged for review.")
        return CheckResult("cold_chain", "NEEDS_REVIEW", confidence, detail, evidence_refs)

    return CheckResult("cold_chain", "PASS", confidence,
                        f"All readings (observed + estimated) within {thresholds.cold_chain_limit_c}C limit.",
                        evidence_refs)


def check_location_coverage(route_pings, route_events, thresholds: ThresholdConfig) -> CheckResult:
    gap = max_gap_minutes(route_pings, "latitude")
    n_total = len(route_pings)
    n_gps = sum(1 for p in route_pings if p.get("latitude") not in (None, ""))
    fallback_available = any(e.get("latitude") not in (None, "") for e in route_events)  # manual stop-log positions

    if n_total == 0:
        return CheckResult("location_traceability", "INSUFFICIENT_DATA", "UNKNOWN",
                            "No location telemetry stream at all for this route.")

    if gap is not None and gap <= thresholds.max_gps_gap_min:
        return CheckResult("location_traceability", "PASS", "OBSERVED",
                            f"GPS coverage continuous (max gap {gap:.0f} min); {n_gps}/{n_total} pings had a fix.",
                            [f"{n_gps}/{n_total} pings with GPS fix"])

    if n_gps == 0:
        gap_desc = "total loss (no GPS fixes at all)"
    elif n_gps == 1:
        gap_desc = "single GPS fix (insufficient to establish continuous track)"
    else:
        gap_desc = f"{gap:.0f} min" if gap is not None else "multiple broken gaps"

    if fallback_available:
        return CheckResult("location_traceability", "PASS", "ESTIMATED",
                            f"GPS gap of {gap_desc} bridged using driver-logged stop "
                            f"coordinates from route_events (fallback source).",
                            [f"{n_gps}/{n_total} pings with GPS fix", "route_events stop coordinates used as fallback"])

    return CheckResult("location_traceability", "NEEDS_REVIEW", "UNKNOWN",
                        f"GPS gap of {gap_desc} with no fallback stop-location log available; "
                        f"route path cannot be fully reconstructed.",
                        [f"{n_gps}/{n_total} pings with GPS fix"])


def check_calibration(device_id, calibration_by_device, batch_formed_time, thresholds: ThresholdConfig) -> CheckResult:
    cal = calibration_by_device.get(device_id)
    if not cal:
        return CheckResult("calibration_validity", "NEEDS_REVIEW", "UNKNOWN",
                            f"No calibration record found for device {device_id}.")
    due = _parse_dt(cal["next_due_date"] + "T23:59:59")
    formed = _parse_dt(batch_formed_time)
    grace = timedelta(days=thresholds.calibration_grace_days)
    if formed and due and formed > due + grace:
        due_date = _parse_dt(cal["next_due_date"]).date()
        overdue_days = max(1, (formed.date() - (due_date + grace)).days)
        return CheckResult("calibration_validity", "FAIL", "OBSERVED",
                            f"Device {device_id} calibration expired {overdue_days} days before this batch "
                            f"was formed (due {cal['next_due_date']}).",
                            [f"last_calibration={cal['last_calibration_date']}", f"offset={cal['calibration_offset_c']}C"])
    return CheckResult("calibration_validity", "PASS", "OBSERVED",
                        f"Device {device_id} calibration valid through {cal['next_due_date']}.",
                        [f"last_calibration={cal['last_calibration_date']}"])


def check_custody_chain(route_handovers, thresholds: ThresholdConfig) -> CheckResult:
    if not route_handovers:
        return CheckResult("custody_chain", "INSUFFICIENT_DATA", "UNKNOWN", "No handover records for this route.")
    broken = [h for h in route_handovers if not h.get("event_time")]
    if broken:
        ids = ", ".join(h.get("handover_id", "UNKNOWN") for h in broken)
        status = "NEEDS_REVIEW" if thresholds.custody_gap_is_blocking else "FAIL"
        return CheckResult("custody_chain", status, "MANUAL",
                            f"{len(broken)} handover(s) missing a captured event time / signature "
                            f"({ids}); a manual custody form is required to close this gap.",
                            [h.get("handover_id", "") for h in route_handovers])
    unsigned = [h for h in route_handovers if h.get("signature_captured") == "NO"]
    if unsigned:
        return CheckResult("custody_chain", "NEEDS_REVIEW", "MIXED",
                            f"{len(unsigned)} handover(s) recorded without signature capture.",
                            [h.get("handover_id", "") for h in route_handovers])
    return CheckResult("custody_chain", "PASS", "OBSERVED",
                        f"Unbroken custody chain across {len(route_handovers)} handover(s).",
                        [h.get("handover_id", "") for h in route_handovers])


def check_route_completion(route_events_for_route, thresholds: ThresholdConfig) -> CheckResult:
    if not route_events_for_route:
        return CheckResult("route_completion", "INSUFFICIENT_DATA", "UNKNOWN", "No route-event log found.")
    missed = [e for e in route_events_for_route if e.get("status") == "MISSED"]
    if missed:
        ids = ", ".join(e.get("producer_id", "UNKNOWN") for e in missed)
        return CheckResult("route_completion", "NEEDS_REVIEW", "OBSERVED",
                            f"{len(missed)} scheduled stop(s) not completed: {ids}.",
                            [f"{len(route_events_for_route)} planned stops"])
    return CheckResult("route_completion", "PASS", "OBSERVED",
                        f"All {len(route_events_for_route)} scheduled stops completed.",
                        [f"{len(route_events_for_route)} planned stops"])


def check_sync_integrity(route_pings, route_handovers=None) -> CheckResult:
    """Reports on store-and-forward health: how much evidence arrived late or never."""
    total = len(route_pings)
    if total == 0:
        return CheckResult("data_sync_integrity", "INSUFFICIENT_DATA", "UNKNOWN", "No telemetry to assess.")
    lost = sum(1 for p in route_pings if p.get("sync_status") == "lost")
    delayed = sum(1 for p in route_pings if p.get("sync_status") == "delayed")
    detail = (f"{lost}/{total} sensor records never synced (store-and-forward loss - would need manual "
              f"retrieval from device), {delayed}/{total} arrived late via store-and-forward but were "
              f"recovered and used (ordered by true event_time, not arrival time).")
    status = "NEEDS_REVIEW" if lost > 0 else "PASS"
    confidence = "MIXED" if (lost or delayed) else "OBSERVED"
    return CheckResult("data_sync_integrity", status, confidence, detail,
                        [f"lost={lost}", f"delayed={delayed}", f"live={total - lost - delayed}"])


# --------------------------------------------------------------------------
# Batch-level orchestration
# --------------------------------------------------------------------------

STATUS_RANK = {"FAIL": 3, "NEEDS_REVIEW": 2, "INSUFFICIENT_DATA": 2, "PASS": 0}


def build_evidence_pack(batch, route_id, sensor_by_route, calibration_by_device,
                         handovers_by_route, route_events_by_route, thresholds: ThresholdConfig) -> EvidencePack:
    pings = sorted(sensor_by_route.get(route_id, []), key=lambda p: str(p.get("event_time") or ""))
    handovers = handovers_by_route.get(route_id, [])
    events = route_events_by_route.get(route_id, [])

    checks = [
        check_cold_chain(pings, thresholds),
        check_location_coverage(pings, events, thresholds),
        check_calibration(batch.get("device_id"), calibration_by_device, batch.get("formed_time"), thresholds),
        check_custody_chain(handovers, thresholds),
        check_route_completion(events, thresholds),
        check_sync_integrity(pings, handovers),
    ]

    worst = max((STATUS_RANK[c.status] for c in checks), default=0)
    overall = {3: "FAIL", 2: "NEEDS_REVIEW"}.get(worst, "PASS")

    evidenced = sum(1 for c in checks if c.confidence in ("OBSERVED", "ESTIMATED", "MIXED"))
    completeness = round(evidenced / len(checks), 2) if checks else 0.0
    if completeness < thresholds.min_evidence_completeness and overall == "PASS":
        overall = "NEEDS_REVIEW"

    return EvidencePack(
        batch_id=batch.get("batch_id", ""),
        route_id=route_id,
        checks=checks,
        overall_status=overall,
        completeness_score=completeness,
        generated_at=datetime.now().isoformat(timespec="seconds") + "Z",
    )


# --------------------------------------------------------------------------
# Public pipeline entrypoint
# --------------------------------------------------------------------------

def run_pipeline(data_dir=None, thresholds: Optional[ThresholdConfig] = None):
    thresholds = thresholds or ThresholdConfig()
    if data_dir is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(base_dir)
        if os.path.isdir("data"):
            data_dir = "data"
        elif os.path.isdir("../data"):
            data_dir = "../data"
        else:
            data_dir = os.path.join(project_root, "data")

    sensor = _read_csv(f"{data_dir}/sensor_logs.csv")
    calibration = _read_csv(f"{data_dir}/calibration.csv")
    handovers = _read_csv(f"{data_dir}/handovers.csv")
    route_events = _read_csv(f"{data_dir}/route_events.csv")
    batches = _read_csv(f"{data_dir}/batches.csv")

    sensor_by_route = {}
    for p in sensor:
        sensor_by_route.setdefault(p["route_id"], []).append(p)

    calibration_by_device = {c["device_id"]: c for c in calibration}

    handovers_by_route = {}
    for h in handovers:
        handovers_by_route.setdefault(h["route_id"], []).append(h)

    route_events_by_route = {}
    for e in route_events:
        route_events_by_route.setdefault(e["route_id"], []).append(e)

    packs = []
    for batch in batches:
        pack = build_evidence_pack(batch, batch["route_id"], sensor_by_route, calibration_by_device,
                                    handovers_by_route, route_events_by_route, thresholds)
        packs.append(pack)
    return packs


if __name__ == "__main__":
    packs = run_pipeline()
    for p in packs:
        print(f"{p.batch_id} ({p.route_id}): {p.overall_status}  completeness={p.completeness_score}")
        for c in p.checks:
            print(f"   - {c.name:22s} {c.status:18s} [{c.confidence}]  {c.detail}")
