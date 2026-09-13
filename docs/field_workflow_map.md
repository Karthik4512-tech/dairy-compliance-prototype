# Field Workflow Map

## Operating environment
A dairy company runs collection **routes**. Each route visits several small
**producers** (farms) in sequence, collecting milk into the truck's tank.
A logger device on the truck records **temperature** and **GPS** periodically.
At each stop a **handover** (custody transfer) is recorded from producer to
driver; at the plant a final handover transfers custody from driver to the
plant gate, and the collected milk is merged into a **product batch**.

Devices in the field are cheap, battery-powered, and often out of cellular
range for parts of the route (rural collection areas) — this is the root
cause of the "disconnected devices and logs" problem in the brief.

## Decisions affected by manually-assembled, disconnected compliance evidence

| Decision | Who makes it | What breaks if evidence is manual/disconnected |
|---|---|---|
| Release a batch for processing vs quarantine it | QA / plant manager | Cold-chain breach may be missed or caught too late (after further processing) |
| Accept/reject a load at the plant gate | Gate inspector | No fast way to check calibration validity of the logger that produced the temperature trail |
| Pay a producer / dispute a shortfall | Finance / ops | Custody chain (who handled how much milk, when) can't be reconstructed quickly |
| Regulatory audit response | Compliance officer | Manually re-assembling 5 disconnected logs per batch is slow, error-prone, and inconsistent across auditors |
| Route/driver performance review | Ops manager | Missed stops or late collections are buried in spreadsheets, not visible until reviewed |
| Device maintenance scheduling | Technician | Expired calibration is only caught retroactively, if at all |

## Current (manual) workflow

```
Producer  --milk-->  Driver  --milk-->  Plant gate  --milk-->  Batch formed
   |paper receipt        |truck logger        |paper handover
   |(sometimes)           (SD card/telemetry)  |form
   v                      v                    v
                    [ Disconnected data sits in: truck SD card,
                      telematics portal, paper handover binder,
                      calibration spreadsheet, route-planning tool ]
                                    |
                    Compliance officer manually pulls each source,
                    eyeballs temperature charts, matches paperwork,
                    ~20-25 min per batch, error-prone, inconsistent
                                    v
                          Compliance report (delayed, manual)
```

## New (automated) workflow implemented by this prototype

```
Producer  --milk-->  Driver  --milk-->  Plant gate  --milk-->  Batch formed
   |handover event        |sensor pings (temp+GPS)   |handover event
   |(app or paper->        |store-and-forward if      |(app)
   | later digitised)      | offline)                  |
   v                       v                            v
        sensor_logs.csv | calibration.csv | handovers.csv | route_events.csv | batches.csv
                                    |
                     Evidence Pack Engine (evidence_pack.py)
                     - joins all 5 sources per batch
                     - denoises + interpolates sensor gaps
                     - falls back to route-log GPS when telemetry GPS is missing
                     - flags (not hides) unrecoverable gaps
                     - applies tunable thresholds
                                    v
                Evidence Pack: PASS / NEEDS_REVIEW / FAIL per check,
                with confidence tags (OBSERVED/ESTIMATED/MANUAL/UNKNOWN)
                                    v
        dashboard.html (human review) + evidence_packs.json (system-of-record)
        + summary.csv (spreadsheet-friendly)
                                    v
        Human reviews ONLY flagged batches (not all of them) -> release/quarantine decision
```

## Where "store-and-forward" / manual fallback sits in this map
- If the truck has no signal, the logger keeps recording locally
  (`sync_status = delayed`) and uploads once back in range — the pipeline
  orders everything by the true `event_time`, not upload time.
- If a record never uploads at all (`sync_status = lost`), the pipeline
  says so explicitly rather than silently treating the gap as "no data =
  no problem."
- If GPS drops out, the pipeline falls back to the driver-logged stop
  coordinates from `route_events` (a manual/lower-frequency source) to
  bridge the gap, and marks that evidence as `ESTIMATED`, not `OBSERVED`.
- If a handover's signature/timestamp is missing, the pipeline flags a
  `MANUAL` custody gap needing a paper fallback form, instead of assuming
  custody was fine.
