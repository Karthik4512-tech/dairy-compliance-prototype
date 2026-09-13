## Case: network_outage

**Injected condition:** Truck loses cellular signal for most of the route; 6 readings arrive 5h late via store-and-forward, 1 reading is never recovered.

**Overall status:** `NEEDS_REVIEW`  |  **Evidence completeness:** 100%

| Check | Status | Confidence | Detail |
|---|---|---|---|
| Cold Chain | PASS | OBSERVED | All readings (observed + estimated) within 6.0C limit. |
| Location Traceability | PASS | OBSERVED | GPS coverage continuous (max gap 6 min); 10/10 pings had a fix. |
| Calibration Validity | PASS | OBSERVED | Device LOG-X calibration valid through 2026-06-30. |
| Custody Chain | PASS | OBSERVED | Unbroken custody chain across 2 handover(s). |
| Route Completion | PASS | OBSERVED | All 1 scheduled stops completed. |
| Data Sync Integrity | NEEDS_REVIEW | MIXED | 1/10 sensor records never synced (store-and-forward loss - would need manual retrieval from device), 6/10 arrived late via store-and-forward but were recovered and used (ordered by true event_time, not arrival time). |
