## Case: combined_worst_case

**Injected condition:** Multiple simultaneous failures: patchy GPS, patchy sensor, delayed network sync, one noise spike, AND a genuine sustained cold-chain excursion buried in the mess. The pipeline must still surface the real excursion without being confused by the surrounding noise/gaps.

**Overall status:** `FAIL`  |  **Evidence completeness:** 100%

| Check | Status | Confidence | Detail |
|---|---|---|---|
| Cold Chain | FAIL | ESTIMATED | Sustained cold-chain excursion above 6.0C for 24 min (threshold 10 min). |
| Location Traceability | PASS | OBSERVED | GPS coverage continuous (max gap 18 min); 11/14 pings had a fix. |
| Calibration Validity | PASS | OBSERVED | Device LOG-X calibration valid through 2026-06-30. |
| Custody Chain | PASS | OBSERVED | Unbroken custody chain across 2 handover(s). |
| Route Completion | PASS | OBSERVED | All 1 scheduled stops completed. |
| Data Sync Integrity | PASS | MIXED | 0/14 sensor records never synced (store-and-forward loss - would need manual retrieval from device), 4/14 arrived late via store-and-forward but were recovered and used (ordered by true event_time, not arrival time). |
