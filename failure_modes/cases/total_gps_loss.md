## Case: total_gps_loss

**Injected condition:** Every GPS field is blank for the whole route (device lost satellite fix, e.g. hilly terrain / cold storage box).

**Overall status:** `PASS`  |  **Evidence completeness:** 100%

| Check | Status | Confidence | Detail |
|---|---|---|---|
| Cold Chain | PASS | OBSERVED | All readings (observed + estimated) within 6.0C limit. |
| Location Traceability | PASS | ESTIMATED | GPS gap of total loss (no GPS fixes at all) bridged using driver-logged stop coordinates from route_events (fallback source). |
| Calibration Validity | PASS | OBSERVED | Device LOG-X calibration valid through 2026-06-30. |
| Custody Chain | PASS | OBSERVED | Unbroken custody chain across 2 handover(s). |
| Route Completion | PASS | OBSERVED | All 1 scheduled stops completed. |
| Data Sync Integrity | PASS | OBSERVED | 0/10 sensor records never synced (store-and-forward loss - would need manual retrieval from device), 0/10 arrived late via store-and-forward but were recovered and used (ordered by true event_time, not arrival time). |
