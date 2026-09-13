## Case: total_sensor_failure

**Injected condition:** Temperature probe fails after the 3rd reading and never recovers for the rest of the route (genuine, unfillable gap).

**Overall status:** `NEEDS_REVIEW`  |  **Evidence completeness:** 100%

| Check | Status | Confidence | Detail |
|---|---|---|---|
| Cold Chain | NEEDS_REVIEW | MIXED | 7 reading(s) at the start/end of the route have no temperature evidence and no neighbouring value to interpolate from (sensor failed and never recovered, or failed before the first reading) - a genuine, unfillable gap. No excursion detected in the data that IS available, but coverage cannot be confirmed complete. |
| Location Traceability | PASS | OBSERVED | GPS coverage continuous (max gap 6 min); 10/10 pings had a fix. |
| Calibration Validity | PASS | OBSERVED | Device LOG-X calibration valid through 2026-06-30. |
| Custody Chain | PASS | OBSERVED | Unbroken custody chain across 2 handover(s). |
| Route Completion | PASS | OBSERVED | All 1 scheduled stops completed. |
| Data Sync Integrity | PASS | OBSERVED | 0/10 sensor records never synced (store-and-forward loss - would need manual retrieval from device), 0/10 arrived late via store-and-forward but were recovered and used (ordered by true event_time, not arrival time). |
