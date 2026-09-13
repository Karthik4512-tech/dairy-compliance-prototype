"""
Functional Application - Compliance Evidence Pack Generator
=============================================================
Command-line entrypoint that runs the full pipeline against a data
directory and emits:
  - reports/evidence_packs.json   (full machine-readable evidence pack per batch)
  - reports/summary.csv           (one row per batch, for spreadsheet review)
  - reports/dashboard.html        (human-facing audit dashboard, no server needed)

Usage:
    python cli.py --data ../data --out ../outputs --config default
    python cli.py --data ../data --out ../outputs --cold-chain-limit 5.0 --min-completeness 0.7
"""
import argparse
import csv
import json
import os
import sys
from dataclasses import asdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from evidence_pack import run_pipeline, ThresholdConfig


def render_html(packs, thresholds, out_path):
    def badge(status):
        color = {"PASS": "#1a7f37", "FAIL": "#c22", "NEEDS_REVIEW": "#b8860b",
                 "INSUFFICIENT_DATA": "#666"}.get(status, "#666")
        return f'<span style="background:{color};color:#fff;padding:2px 10px;border-radius:10px;font-size:12px;font-weight:600">{status}</span>'

    def conf_badge(conf):
        color = {"OBSERVED": "#1a7f37", "ESTIMATED": "#0969da", "MANUAL": "#9a6700",
                 "UNKNOWN": "#c22", "MIXED": "#6639ba"}.get(conf, "#666")
        return f'<span style="border:1px solid {color};color:{color};padding:1px 7px;border-radius:8px;font-size:11px">{conf}</span>'

    n_pass = sum(1 for p in packs if p.overall_status == "PASS")
    n_fail = sum(1 for p in packs if p.overall_status == "FAIL")
    n_review = sum(1 for p in packs if p.overall_status == "NEEDS_REVIEW")
    n_insuf = sum(1 for p in packs if p.overall_status == "INSUFFICIENT_DATA")
    avg_completeness = round(sum(p.completeness_score for p in packs) / len(packs), 2) if packs else 0

    rows_html = []
    for p in packs:
        checks_html = "".join(
            f'<tr><td>{c.name.replace("_"," ").title()}</td><td>{badge(c.status)}</td>'
            f'<td>{conf_badge(c.confidence)}</td><td class="detail">{c.detail}</td></tr>'
            for c in p.checks
        )
        rows_html.append(f'''
        <div class="pack">
          <div class="pack-head">
            <h3>{p.batch_id} <span class="muted">({p.route_id})</span></h3>
            <div>{badge(p.overall_status)} <span class="muted" style="margin-left:10px">completeness {p.completeness_score*100:.0f}%</span></div>
          </div>
          <table>
            <thead><tr><th>Check</th><th>Status</th><th>Evidence</th><th>Detail</th></tr></thead>
            <tbody>{checks_html}</tbody>
          </table>
        </div>''')

    html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Dairy Compliance Evidence Packs</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; background:#f6f7f9; margin:0; padding:24px; color:#1b1f24;}}
  h1 {{ font-size:22px; margin-bottom:4px;}}
  .muted {{ color:#666; font-weight:400; font-size:13px;}}
  .summary {{ display:flex; gap:16px; margin: 16px 0 28px;}}
  .stat {{ background:#fff; border:1px solid #e3e5e8; border-radius:10px; padding:14px 20px; min-width:120px;}}
  .stat .num {{ font-size:26px; font-weight:700; }}
  .stat .lbl {{ font-size:12px; color:#666; text-transform:uppercase; letter-spacing:.03em;}}
  .pack {{ background:#fff; border:1px solid #e3e5e8; border-radius:10px; padding:16px 20px; margin-bottom:16px;}}
  .pack-head {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;}}
  table {{ width:100%; border-collapse:collapse; font-size:13px;}}
  th {{ text-align:left; color:#666; font-weight:600; font-size:11px; text-transform:uppercase; padding:6px 8px; border-bottom:1px solid #eee;}}
  td {{ padding:7px 8px; border-bottom:1px solid #f0f0f0; vertical-align:top;}}
  td.detail {{ color:#333;}}
  .config {{ font-size:12px; color:#666; background:#fff; border:1px solid #e3e5e8; border-radius:10px; padding:12px 16px; margin-bottom:20px;}}
</style></head>
<body>
  <h1>Compliance Evidence Pack Dashboard</h1>
  <div class="muted">Automated join of sensor logs, calibration, custody handovers, route events and product batches.</div>
  <div class="summary">
    <div class="stat"><div class="num">{len(packs)}</div><div class="lbl">Batches</div></div>
    <div class="stat"><div class="num" style="color:#1a7f37">{n_pass}</div><div class="lbl">Pass</div></div>
    <div class="stat"><div class="num" style="color:#b8860b">{n_review}</div><div class="lbl">Needs review</div></div>
    <div class="stat"><div class="num" style="color:#c22">{n_fail}</div><div class="lbl">Fail</div></div>
    <div class="stat"><div class="num">{avg_completeness*100:.0f}%</div><div class="lbl">Avg evidence completeness</div></div>
  </div>
  <div class="config">
    Thresholds in effect &mdash; cold-chain limit: {thresholds.cold_chain_limit_c}&deg;C,
    excursion min duration: {thresholds.excursion_min_duration_min} min,
    noise z-score: {thresholds.noise_spike_zscore}, max sensor/GPS gap: {thresholds.max_sensor_gap_min} min,
    min evidence completeness for auto-pass: {thresholds.min_evidence_completeness*100:.0f}%.
  </div>
  {"".join(rows_html)}
</body></html>'''
    with open(out_path, "w") as f:
        f.write(html)


def main():
    PROJECT_ROOT = os.path.dirname(BASE_DIR)
    default_data = "data" if os.path.isdir("data") else ("../data" if os.path.isdir("../data") else os.path.join(PROJECT_ROOT, "data"))
    default_out = "outputs" if os.path.isdir("outputs") or not os.path.isdir("../outputs") else "../outputs"

    ap = argparse.ArgumentParser(description="Generate dairy compliance evidence packs.")
    ap.add_argument("--data", default=default_data)
    ap.add_argument("--out", default=default_out)
    ap.add_argument("--cold-chain-limit", type=float, default=6.0)
    ap.add_argument("--excursion-min-duration", type=int, default=10)
    ap.add_argument("--noise-zscore", type=float, default=3.0)
    ap.add_argument("--max-sensor-gap", type=int, default=20)
    ap.add_argument("--max-gps-gap", type=int, default=20)
    ap.add_argument("--min-completeness", type=float, default=0.6)
    args = ap.parse_args()

    thresholds = ThresholdConfig(
        cold_chain_limit_c=args.cold_chain_limit,
        excursion_min_duration_min=args.excursion_min_duration,
        noise_spike_zscore=args.noise_zscore,
        max_sensor_gap_min=args.max_sensor_gap,
        max_gps_gap_min=args.max_gps_gap,
        min_evidence_completeness=args.min_completeness,
    )

    packs = run_pipeline(args.data, thresholds)

    os.makedirs(args.out, exist_ok=True)

    # JSON evidence packs (full detail, machine-readable)
    json_out = [
        {
            "batch_id": p.batch_id, "route_id": p.route_id, "overall_status": p.overall_status,
            "completeness_score": p.completeness_score, "generated_at": p.generated_at,
            "checks": [asdict(c) for c in p.checks],
        } for p in packs
    ]
    with open(f"{args.out}/evidence_packs.json", "w") as f:
        json.dump(json_out, f, indent=2)

    # CSV summary
    with open(f"{args.out}/summary.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["batch_id", "route_id", "overall_status", "completeness_score",
                    "cold_chain", "location", "calibration", "custody", "route_completion", "sync_integrity"])
        for p in packs:
            by_name = {c.name: c.status for c in p.checks}
            w.writerow([p.batch_id, p.route_id, p.overall_status, p.completeness_score,
                        by_name.get("cold_chain"), by_name.get("location_traceability"),
                        by_name.get("calibration_validity"), by_name.get("custody_chain"),
                        by_name.get("route_completion"), by_name.get("data_sync_integrity")])

    render_html(packs, thresholds, f"{args.out}/dashboard.html")

    n_pass = sum(1 for p in packs if p.overall_status == "PASS")
    n_fail = sum(1 for p in packs if p.overall_status == "FAIL")
    n_review = sum(1 for p in packs if p.overall_status == "NEEDS_REVIEW")
    print(f"Processed {len(packs)} batches -> {n_pass} PASS, {n_review} NEEDS_REVIEW, {n_fail} FAIL")
    print(f"Reports written to {args.out}/ (evidence_packs.json, summary.csv, dashboard.html)")


if __name__ == "__main__":
    main()
