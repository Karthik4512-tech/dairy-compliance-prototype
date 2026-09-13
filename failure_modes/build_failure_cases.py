"""
Failure-mode / edge-case demonstration harness.

Builds four small, hand-crafted single-route datasets, each isolating one
failure condition, and runs them through the same evidence_pack pipeline
used in production. Prints + saves the pipeline's behaviour so the fallback
logic can be inspected directly rather than taken on faith.

Cases:
  1. total_gps_loss        - GPS fails for the entire route; only route_events
                             stop-log positions are available.
  2. network_outage        - the logger buffers everything locally and only
                             syncs hours later (store-and-forward), with one
                             ping never syncing at all.
  3. total_sensor_failure  - the temperature sensor dies mid-route; no
                             fallback source exists at all (genuine gap).
  4. combined_worst_case   - GPS + sensor + network problems together, plus
                             a genuine cold-chain excursion hiding in the
                             noisy data, to show the pipeline still surfaces
                             the real safety issue instead of getting lost
                             in the noise.
"""
import csv
import os
import sys
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
APP_DIR = os.path.join(PROJECT_ROOT, "app")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from evidence_pack import build_evidence_pack, ThresholdConfig  # noqa: E402

OUT_DIR = os.path.join(BASE_DIR, "cases")
os.makedirs(OUT_DIR, exist_ok=True)

T0 = datetime(2026, 3, 2, 7, 0)


def times(n, step_min=6, start=T0):
    return [start + timedelta(minutes=i * step_min) for i in range(n)]


def base_route(route_id, n_pings=10):
    ts = times(n_pings)
    sensor = [{"device_id": "LOG-X", "route_id": route_id, "event_time": t.isoformat(),
               "sync_time": t.isoformat(), "sync_status": "live",
               "temperature_c": round(4.0 + 0.3 * (i % 3), 2),
               "latitude": round(15.90 + i * 0.001, 6), "longitude": round(80.30 + i * 0.001, 6)}
              for i, t in enumerate(ts)]
    handovers = [
        {"handover_id": f"HO-{route_id}-1", "route_id": route_id, "stage": "producer_to_driver",
         "producer_id": "P-01", "from_party": "P-01", "to_party": "Driver",
         "quantity_l": "40", "event_time": ts[0].isoformat(), "signature_captured": "YES", "note": ""},
        {"handover_id": f"HO-{route_id}-PLANT", "route_id": route_id, "stage": "driver_to_plant",
         "producer_id": "", "from_party": "Driver", "to_party": "PLANT-GATE",
         "quantity_l": "40", "event_time": ts[-1].isoformat(), "signature_captured": "YES", "note": ""},
    ]
    route_events = [
        {"route_id": route_id, "stop_seq": 1, "producer_id": "P-01", "planned_time": ts[0].isoformat(),
         "actual_arrival_time": ts[0].isoformat(), "status": "COMPLETED", "truck_id": "TRK-X",
         "driver": "Test Driver", "latitude": 15.90, "longitude": 80.30},
    ]
    calibration_by_device = {"LOG-X": {"device_id": "LOG-X", "last_calibration_date": "2026-01-01",
                                        "calibration_interval_days": "180",
                                        "calibration_offset_c": "0.1", "next_due_date": "2026-06-30",
                                        "technician": "A.Rao"}}
    batch = {"batch_id": f"B-{route_id}", "route_id": route_id, "device_id": "LOG-X",
             "formed_time": (ts[-1] + timedelta(minutes=15)).isoformat(),
             "total_volume_l": "40", "producer_ids": "P-01", "quality_test_result": "PASS"}
    return sensor, handovers, route_events, calibration_by_device, batch


def case_total_gps_loss():
    route_id = "R-GPS-LOSS"
    sensor, handovers, route_events, calib, batch = base_route(route_id)
    for p in sensor:
        p["latitude"] = ""
        p["longitude"] = ""
    return route_id, sensor, handovers, route_events, calib, batch, \
        "Every GPS field is blank for the whole route (device lost satellite fix, e.g. hilly terrain / cold storage box)."


def case_network_outage():
    route_id = "R-NET-OUTAGE"
    sensor, handovers, route_events, calib, batch = base_route(route_id)
    for i, p in enumerate(sensor):
        event_t = datetime.fromisoformat(p["event_time"])
        if i < 6:
            # buffered locally, syncs 5 hours later (store-and-forward)
            p["sync_time"] = (event_t + timedelta(hours=5)).isoformat()
            p["sync_status"] = "delayed"
        elif i == 6:
            # never makes it - simulates a device that is later swapped out
            p["sync_time"] = ""
            p["sync_status"] = "lost"
    return route_id, sensor, handovers, route_events, calib, batch, \
        "Truck loses cellular signal for most of the route; 6 readings arrive 5h late via store-and-forward, 1 reading is never recovered."


def case_total_sensor_failure():
    route_id = "R-SENSOR-FAIL"
    sensor, handovers, route_events, calib, batch = base_route(route_id)
    for i, p in enumerate(sensor):
        if i >= 3:
            p["temperature_c"] = ""  # sensor dies from stop 4 onward, never recovers
    return route_id, sensor, handovers, route_events, calib, batch, \
        "Temperature probe fails after the 3rd reading and never recovers for the rest of the route (genuine, unfillable gap)."


def case_combined_worst_case():
    route_id = "R-WORST-CASE"
    sensor, handovers, route_events, calib, batch = base_route(route_id, n_pings=14)
    # hide a real excursion in the middle
    for i, p in enumerate(sensor):
        if 5 <= i <= 9:
            p["temperature_c"] = round(7.5 + 0.4 * (i - 5), 2)  # genuine sustained excursion
        if i in (2, 3, 10):
            p["latitude"] = ""
            p["longitude"] = ""  # GPS dropouts
        if i in (1, 11):
            p["temperature_c"] = ""  # sensor dropouts (should be interpolated, bridging real neighbours)
        if i == 6:
            p["temperature_c"] = round(float(p["temperature_c"]) + 25, 2)  # one wild noise spike on top
        event_t = datetime.fromisoformat(p["event_time"])
        if i % 4 == 0:
            p["sync_time"] = (event_t + timedelta(hours=2)).isoformat()
            p["sync_status"] = "delayed"
    route_events[0]["latitude"] = 15.90
    route_events[0]["longitude"] = 80.30
    return route_id, sensor, handovers, route_events, calib, batch, \
        ("Multiple simultaneous failures: patchy GPS, patchy sensor, delayed network sync, one noise spike, "
         "AND a genuine sustained cold-chain excursion buried in the mess. The pipeline must still surface "
         "the real excursion without being confused by the surrounding noise/gaps.")


def run_case(name, builder, thresholds):
    route_id, sensor, handovers, route_events, calib, batch, description = builder()
    sensor_by_route = {route_id: sensor}
    handovers_by_route = {route_id: handovers}
    route_events_by_route = {route_id: route_events}
    pack = build_evidence_pack(batch, route_id, sensor_by_route, calib, handovers_by_route,
                                route_events_by_route, thresholds)

    lines = [f"## Case: {name}", "", f"**Injected condition:** {description}", "",
             f"**Overall status:** `{pack.overall_status}`  |  **Evidence completeness:** {pack.completeness_score*100:.0f}%", "",
             "| Check | Status | Confidence | Detail |", "|---|---|---|---|"]
    for c in pack.checks:
        lines.append(f"| {c.name.replace('_',' ').title()} | {c.status} | {c.confidence} | {c.detail} |")
    lines.append("")
    text = "\n".join(lines)
    with open(f"{OUT_DIR}/{name}.md", "w") as f:
        f.write(text)
    print(text)
    print("\n" + "=" * 90 + "\n")
    return pack


if __name__ == "__main__":
    thresholds = ThresholdConfig(excursion_min_duration_min=10, max_sensor_gap_min=20, max_gps_gap_min=20)
    cases = [
        ("total_gps_loss", case_total_gps_loss),
        ("network_outage", case_network_outage),
        ("total_sensor_failure", case_total_sensor_failure),
        ("combined_worst_case", case_combined_worst_case),
    ]
    results = []
    for name, builder in cases:
        pack = run_case(name, builder, thresholds)
        results.append((name, pack))

    with open(f"{OUT_DIR}/_index.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case", "overall_status", "completeness_score"])
        for name, pack in results:
            w.writerow([name, pack.overall_status, pack.completeness_score])
