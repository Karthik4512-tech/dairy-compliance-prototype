"""
Synthetic data generator for the Dairy Compliance Evidence Pack prototype.

Simulates one operating day for a milk-collection company running several
routes. Each route visits a number of small producers, picks up milk in
churns/cans, transports it (with an onboard temperature + GPS logger) to a
processing plant, where it is merged into product batches.

Five data streams are produced, mirroring what a real fleet would emit from
disconnected devices/logs:

  1. sensor_logs.csv     - temperature + GPS pings from the truck logger
  2. calibration.csv     - calibration history for each logger device
  3. handovers.csv       - custody transfer events (producer->driver->plant)
  4. route_events.csv    - planned vs actual stop events for each route
  5. batches.csv         - product batches formed at the plant from handovers

Realism / messiness injected on purpose (tunable via CONFIG below):
  - GPS dropout (device loses satellite fix, especially in valleys)
  - Sensor dropout (logger battery / wiring fault -> missing readings)
  - Sensor noise (spikes from vibration / bad contact)
  - Network dropout -> store-and-forward: records are generated with a true
    `event_time`, but are not "synced" to the server until a later
    `sync_time`. Some are only ever recovered via manual fallback forms.
  - A handful of expired-calibration devices, temperature excursions, missed
    stops, and a short custody gap, so the evidence pack has real problems
    to catch.

Run:  python generate_data.py [--seed 42] [--out ../data]
"""
import argparse
import csv
import math
import random
from datetime import datetime, timedelta

# --------------------------------------------------------------------------
# CONFIG - tune scenario "messiness" here
# --------------------------------------------------------------------------
CONFIG = {
    "n_routes": 30,
    "producers_per_route": (5, 9),          # min, max
    "gps_dropout_rate": 0.12,               # fraction of pings missing GPS
    "sensor_dropout_rate": 0.08,            # fraction of pings missing temp
    "sensor_noise_rate": 0.05,              # fraction of pings that are noise spikes
    "sensor_noise_magnitude": 8.0,          # +/- degC spike size
    "network_delay_rate": 0.20,             # fraction of records store-and-forward delayed
    "network_delay_minutes": (30, 600),     # sync delay range when delayed
    "network_lost_rate": 0.03,              # fraction of records NEVER synced (manual fallback needed)
    "excursion_route_fraction": 0.25,       # fraction of routes with a genuine cold-chain excursion
    "expired_calibration_fraction": 0.15,   # fraction of devices with expired calibration
    "missed_stop_fraction": 0.08,           # fraction of stops the driver skips/fails
    "custody_gap_fraction": 0.10,           # fraction of routes with a broken custody chain link
    "cold_chain_limit_c": 6.0,              # regulatory max holding temp
    "ping_interval_minutes": 6,
}

BASE_DATE = datetime(2026, 3, 2, 5, 30)  # operating day start, 05:30


def jitter_latlon(lat, lon, meters=300):
    d = meters / 111_000.0
    return lat + random.uniform(-d, d), lon + random.uniform(-d, d)


def make_route_geography(n_stops, origin=(15.9, 80.3)):
    """Fabricate a simple chain of stop coordinates + a plant at the end."""
    pts = [origin]
    lat, lon = origin
    for _ in range(n_stops):
        lat, lon = jitter_latlon(lat, lon, meters=random.randint(1500, 5000))
        pts.append((lat, lon))
    plant = jitter_latlon(lat, lon, meters=random.randint(2000, 6000))
    pts.append(plant)
    return pts


def sync_time_for(event_time, rng):
    """Decide whether/when a record reaches the server (store-and-forward)."""
    r = rng.random()
    if r < CONFIG["network_lost_rate"]:
        return None, "lost"  # never synced -> needs manual fallback
    if r < CONFIG["network_lost_rate"] + CONFIG["network_delay_rate"]:
        delay = rng.randint(*CONFIG["network_delay_minutes"])
        return event_time + timedelta(minutes=delay), "delayed"
    return event_time + timedelta(minutes=rng.randint(0, 3)), "live"


def gen_calibration(devices, rng):
    rows = []
    for dev in devices:
        interval_days = 180
        expired = rng.random() < CONFIG["expired_calibration_fraction"]
        if expired:
            last_cal = BASE_DATE - timedelta(days=rng.randint(interval_days + 1, interval_days + 200))
        else:
            last_cal = BASE_DATE - timedelta(days=rng.randint(10, interval_days - 20))
        offset = round(rng.uniform(-0.3, 0.3), 2)
        rows.append({
            "device_id": dev,
            "last_calibration_date": last_cal.date().isoformat(),
            "calibration_interval_days": interval_days,
            "calibration_offset_c": offset,
            "next_due_date": (last_cal + timedelta(days=interval_days)).date().isoformat(),
            "technician": rng.choice(["A.Rao", "S.Kumar", "P.Naidu"]),
        })
    return rows


def gen_route_data(route_id, rng, all_sensor, all_calib_devices, all_handovers,
                    all_route_events, all_batches):
    n_stops = rng.randint(*CONFIG["producers_per_route"])
    geo = make_route_geography(n_stops)
    device_id = f"LOG-{route_id:03d}"
    all_calib_devices.append(device_id)
    truck_id = f"TRK-{route_id:03d}"
    driver = rng.choice(["Ravi K.", "Lakshmi P.", "Suresh N.", "Anitha V.", "Mahesh R."])

    t = BASE_DATE + timedelta(minutes=rng.randint(0, 40))
    excursion_route = rng.random() < CONFIG["excursion_route_fraction"]
    excursion_start = rng.randint(2, max(2, n_stops - 1)) if excursion_route else None
    custody_gap_here = rng.random() < CONFIG["custody_gap_fraction"]
    gap_at_stop = rng.randint(2, n_stops) if custody_gap_here else None

    handover_chain = []
    milk_volume_total = 0.0
    producers_in_batch = []
    any_missed = False
    any_expired_calibration = False  # filled in by caller after calibration is generated

    for stop_idx in range(1, n_stops + 1):
        lat, lon = geo[stop_idx]
        producer_id = f"P-{route_id:02d}{stop_idx:02d}"
        planned_time = t
        # driver running early/late
        actual_time = planned_time + timedelta(minutes=rng.randint(-5, 25))
        missed = rng.random() < CONFIG["missed_stop_fraction"]
        if missed:
            any_missed = True

        all_route_events.append({
            "route_id": f"R-{route_id:03d}",
            "stop_seq": stop_idx,
            "producer_id": producer_id,
            "planned_time": planned_time.isoformat(),
            "actual_arrival_time": "" if missed else actual_time.isoformat(),
            "status": "MISSED" if missed else "COMPLETED",
            "truck_id": truck_id,
            "driver": driver,
            "latitude": "" if missed else round(lat, 6),
            "longitude": "" if missed else round(lon, 6),
        })

        # sensor pings clustered around the stop + transit to next stop
        for k in range(3):
            ping_time = actual_time + timedelta(minutes=k * CONFIG["ping_interval_minutes"])
            temp = round(rng.uniform(3.0, 5.0), 2)
            if excursion_route and excursion_start is not None and stop_idx >= excursion_start:
                temp = round(rng.uniform(6.5, 9.5), 2)  # genuine cold-chain excursion
            if rng.random() < CONFIG["sensor_noise_rate"]:
                temp = round(temp + rng.choice([-1, 1]) * CONFIG["sensor_noise_magnitude"] * rng.uniform(0.5, 1.0), 2)
            has_temp = rng.random() >= CONFIG["sensor_dropout_rate"]
            has_gps = rng.random() >= CONFIG["gps_dropout_rate"]
            plat, plon = jitter_latlon(lat, lon, meters=150)
            sync_ts, sync_status = sync_time_for(ping_time, rng)
            all_sensor.append({
                "device_id": device_id,
                "route_id": f"R-{route_id:03d}",
                "event_time": ping_time.isoformat(),
                "sync_time": sync_ts.isoformat() if sync_ts else "",
                "sync_status": sync_status,
                "temperature_c": temp if has_temp else "",
                "latitude": round(plat, 6) if has_gps else "",
                "longitude": round(plon, 6) if has_gps else "",
            })

        if not missed:
            qty = round(rng.uniform(18, 65), 1)
            milk_volume_total += qty
            producers_in_batch.append(producer_id)
            ho_time = actual_time + timedelta(minutes=rng.randint(2, 6))
            broken = (gap_at_stop is not None and stop_idx == gap_at_stop)
            handover_chain.append({
                "handover_id": f"HO-{route_id:03d}-{stop_idx:02d}",
                "route_id": f"R-{route_id:03d}",
                "stage": "producer_to_driver",
                "producer_id": producer_id,
                "from_party": producer_id,
                "to_party": driver,
                "quantity_l": qty,
                "event_time": "" if broken else ho_time.isoformat(),
                "signature_captured": "NO" if broken else "YES",
                "note": "signature/device fault - custody gap" if broken else "",
            })
        t = actual_time + timedelta(minutes=rng.randint(8, 22))

    # final handover: driver -> plant
    plant_arrival = t + timedelta(minutes=rng.randint(20, 45))
    handover_chain.append({
        "handover_id": f"HO-{route_id:03d}-PLANT",
        "route_id": f"R-{route_id:03d}",
        "stage": "driver_to_plant",
        "producer_id": "",
        "from_party": driver,
        "to_party": "PLANT-GATE",
        "quantity_l": round(milk_volume_total, 1),
        "event_time": plant_arrival.isoformat(),
        "signature_captured": "YES",
        "note": "",
    })
    all_handovers.extend(handover_chain)

    batch_id = f"B-{route_id:03d}"
    all_batches.append({
        "batch_id": batch_id,
        "route_id": f"R-{route_id:03d}",
        "device_id": device_id,
        "formed_time": (plant_arrival + timedelta(minutes=10)).isoformat(),
        "total_volume_l": round(milk_volume_total, 1),
        "producer_ids": "|".join(producers_in_batch),
        "quality_test_result": rng.choice(["PASS", "PASS", "PASS", "PASS", "FLAG-ACIDITY"]),
    })

    return {
        "route_id": f"R-{route_id:03d}",
        "batch_id": batch_id,
        "device_id": device_id,
        "true_cold_chain_excursion": bool(excursion_route),
        "true_custody_gap": bool(custody_gap_here),
        "true_missed_stop": bool(any_missed),
    }


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    import os
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(BASE_DIR)
    default_out = "data" if os.path.isdir("data") else ("../data" if os.path.isdir("../data") else os.path.join(PROJECT_ROOT, "data"))

    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=str, default=default_out)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    random.seed(args.seed)

    sensor, calib_devices, handovers, route_events, batches = [], [], [], [], []
    ground_truth = []

    for route_id in range(1, CONFIG["n_routes"] + 1):
        gt = gen_route_data(route_id, rng, sensor, calib_devices, handovers, route_events, batches)
        ground_truth.append(gt)

    calibration = gen_calibration(calib_devices, rng)

    # backfill true expired-calibration flag now that calibration exists
    from datetime import date
    calib_by_device = {c["device_id"]: c for c in calibration}
    batch_by_id = {b["batch_id"]: b for b in batches}
    for gt in ground_truth:
        cal = calib_by_device[gt["device_id"]]
        formed = datetime.fromisoformat(batch_by_id[gt["batch_id"]]["formed_time"])
        due = datetime.fromisoformat(cal["next_due_date"] + "T23:59:59")
        gt["true_calibration_expired"] = formed > due

    import os
    os.makedirs(args.out, exist_ok=True)

    write_csv(f"{args.out}/sensor_logs.csv", sensor,
              ["device_id", "route_id", "event_time", "sync_time", "sync_status",
               "temperature_c", "latitude", "longitude"])
    write_csv(f"{args.out}/calibration.csv", calibration,
              ["device_id", "last_calibration_date", "calibration_interval_days",
               "calibration_offset_c", "next_due_date", "technician"])
    write_csv(f"{args.out}/handovers.csv", handovers,
              ["handover_id", "route_id", "stage", "producer_id", "from_party", "to_party",
               "quantity_l", "event_time", "signature_captured", "note"])
    write_csv(f"{args.out}/route_events.csv", route_events,
              ["route_id", "stop_seq", "producer_id", "planned_time", "actual_arrival_time",
               "status", "truck_id", "driver", "latitude", "longitude"])
    write_csv(f"{args.out}/batches.csv", batches,
              ["batch_id", "route_id", "device_id", "formed_time", "total_volume_l",
               "producer_ids", "quality_test_result"])
    write_csv(f"{args.out}/ground_truth.csv", ground_truth,
              ["route_id", "batch_id", "device_id", "true_cold_chain_excursion",
               "true_custody_gap", "true_missed_stop", "true_calibration_expired"])

    print(f"Generated: {len(sensor)} sensor pings, {len(calibration)} calibration records, "
          f"{len(handovers)} handovers, {len(route_events)} route events, {len(batches)} batches "
          f"-> {args.out}")


if __name__ == "__main__":
    main()
