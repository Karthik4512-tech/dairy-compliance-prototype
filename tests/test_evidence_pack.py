"""
Regression and unit test suite for the Dairy Compliance Evidence Pack engine.
Tests all core checks, edge cases, boundary conditions, and robustness.
"""
import os
import sys
import unittest

# Ensure app is importable from anywhere
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
APP_DIR = os.path.join(PROJECT_ROOT, "app")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from evidence_pack import (
    ThresholdConfig,
    clean_sensor_series,
    interpolate_gaps,
    check_cold_chain,
    check_location_coverage,
    check_calibration,
    check_custody_chain,
    check_route_completion,
    check_sync_integrity,
    build_evidence_pack,
    run_pipeline,
)


class TestEvidencePackRegression(unittest.TestCase):

    def setUp(self):
        self.thresholds = ThresholdConfig(
            cold_chain_limit_c=6.0,
            excursion_min_duration_min=10,
            noise_spike_zscore=3.0,
            max_sensor_gap_min=20,
            max_gps_gap_min=20,
        )

    # --------------------------------------------------------------------------
    # 1. Flat baseline noise filter regression test
    # --------------------------------------------------------------------------
    def test_flat_baseline_wild_spike(self):
        """A wild 25.0°C temperature spike on a constant 4.0°C baseline must be rejected as noise."""
        pings = [
            {"event_time": f"2026-03-02T06:{i:02d}:00", "temperature_c": 4.0}
            for i in range(10)
        ]
        pings[5]["temperature_c"] = 25.0  # isolated wild noise spike

        cleaned, stats = clean_sensor_series(pings, self.thresholds)
        self.assertEqual(stats["n_noise_rejected"], 1, "Expected exactly 1 noise spike rejected")
        self.assertEqual(cleaned[5]["flag"], "NOISE_REJECTED")
        self.assertIsNone(cleaned[5]["temperature_c"])
        self.assertEqual(cleaned[5]["raw_value"], 25.0)

        # Cold chain check on this series should pass after interpolation
        res = check_cold_chain(pings, self.thresholds)
        self.assertEqual(res.status, "PASS", f"Expected PASS after rejecting spike, got {res.status}: {res.detail}")

    def test_flat_baseline_normal_slight_variation_not_rejected(self):
        """Small acceptable sensor reading variations (e.g. 4.1°C) must NOT be flagged as noise."""
        pings = [
            {"event_time": f"2026-03-02T06:{i:02d}:00", "temperature_c": 4.0}
            for i in range(10)
        ]
        pings[5]["temperature_c"] = 4.15  # normal slight variation

        cleaned, stats = clean_sensor_series(pings, self.thresholds)
        self.assertEqual(stats["n_noise_rejected"], 0, "Normal variation should not be rejected as noise")
        self.assertEqual(cleaned[5]["flag"], "OBSERVED")

    # --------------------------------------------------------------------------
    # 2. Calibration expiry boundary logic
    # --------------------------------------------------------------------------
    def test_same_day_calibration_expiry_boundary(self):
        """A calibration due on 2026-03-02 must NOT be reported as expired at 05:30 on 2026-03-02."""
        cal = {
            "LOG-TEST": {
                "device_id": "LOG-TEST",
                "next_due_date": "2026-03-02",
                "last_calibration_date": "2025-09-02",
                "calibration_offset_c": "0.1",
            }
        }
        # Batch formed in the morning on the due date
        res_same_day = check_calibration("LOG-TEST", cal, "2026-03-02T05:30:00", self.thresholds)
        self.assertEqual(res_same_day.status, "PASS", f"Calibration on due date should PASS, got: {res_same_day}")
        self.assertIn("valid through 2026-03-02", res_same_day.detail)

        # Batch formed the following day (2026-03-03) should expire
        res_next_day = check_calibration("LOG-TEST", cal, "2026-03-03T05:30:00", self.thresholds)
        self.assertEqual(res_next_day.status, "FAIL", "Calibration 1 day after due date should FAIL")
        self.assertIn("expired 1 days before", res_next_day.detail)

    def test_calibration_grace_days(self):
        """Calibration check should respect grace period."""
        th_grace = ThresholdConfig(calibration_grace_days=2)
        cal = {
            "LOG-TEST": {
                "device_id": "LOG-TEST",
                "next_due_date": "2026-03-02",
                "last_calibration_date": "2025-09-02",
                "calibration_offset_c": "0.1",
            }
        }
        # 1 day past due date, but within 2-day grace period
        res = check_calibration("LOG-TEST", cal, "2026-03-03T10:00:00", th_grace)
        self.assertEqual(res.status, "PASS")

        # 3 days past due date (exceeds grace period)
        res_expired = check_calibration("LOG-TEST", cal, "2026-03-05T10:00:00", th_grace)
        self.assertEqual(res_expired.status, "FAIL")

    # --------------------------------------------------------------------------
    # 3. Excursion duration calculation
    # --------------------------------------------------------------------------
    def test_excursion_duration_excludes_recovery(self):
        """The reported excursion duration represents the actual period outside permitted range and does not include recovery ping."""
        # 06:00 (7.0°C - over), 06:06 (7.0°C - over), 06:12 (7.0°C - over), 06:18 (5.0°C - safe)
        # Period outside permitted range is 06:00 to 06:12 = 12 minutes (NOT 18 minutes).
        pings = [
            {"event_time": "2026-03-02T06:00:00", "temperature_c": 7.0},
            {"event_time": "2026-03-02T06:06:00", "temperature_c": 7.0},
            {"event_time": "2026-03-02T06:12:00", "temperature_c": 7.0},
            {"event_time": "2026-03-02T06:18:00", "temperature_c": 5.0},
            {"event_time": "2026-03-02T06:24:00", "temperature_c": 5.0},
        ]
        res = check_cold_chain(pings, self.thresholds)
        self.assertEqual(res.status, "FAIL")
        self.assertIn("excursion above 6.0C for 12 min", res.detail)

    def test_excursion_duration_at_final_reading(self):
        """Correctly calculate duration when excursion continues to the final reading of the route."""
        # 06:00 (5.0°C), 06:06 (7.5°C), 06:12 (7.5°C), 06:18 (7.5°C) -> duration 06:06 to 06:18 = 12 min
        pings = [
            {"event_time": "2026-03-02T06:00:00", "temperature_c": 5.0},
            {"event_time": "2026-03-02T06:06:00", "temperature_c": 7.5},
            {"event_time": "2026-03-02T06:12:00", "temperature_c": 7.5},
            {"event_time": "2026-03-02T06:18:00", "temperature_c": 7.5},
        ]
        res = check_cold_chain(pings, self.thresholds)
        self.assertEqual(res.status, "FAIL")
        self.assertIn("excursion above 6.0C for 12 min", res.detail)

    # --------------------------------------------------------------------------
    # 4. Single GPS fix description vs zero vs multiple
    # --------------------------------------------------------------------------
    def test_single_gps_fix_description(self):
        """Single GPS fix must not be described as 'total GPS loss'."""
        pings = [{"event_time": "2026-03-02T06:00:00", "latitude": "15.90", "longitude": "80.30"}]
        events_with_fallback = [{"latitude": 15.90, "longitude": 80.30}]
        events_without_fallback = []

        res_fallback = check_location_coverage(pings, events_with_fallback, self.thresholds)
        self.assertNotIn("total loss", res_fallback.detail)
        self.assertIn("single GPS fix", res_fallback.detail)
        self.assertEqual(res_fallback.status, "PASS")

        res_no_fallback = check_location_coverage(pings, events_without_fallback, self.thresholds)
        self.assertNotIn("total loss", res_no_fallback.detail)
        self.assertIn("single GPS fix", res_no_fallback.detail)
        self.assertEqual(res_no_fallback.status, "NEEDS_REVIEW")

    def test_zero_gps_fix_description(self):
        """Zero GPS fixes must be accurately described as total loss."""
        pings = [{"event_time": "2026-03-02T06:00:00", "latitude": "", "longitude": ""}]
        events = [{"latitude": 15.90, "longitude": 80.30}]
        res = check_location_coverage(pings, events, self.thresholds)
        self.assertIn("total loss", res.detail)

    # --------------------------------------------------------------------------
    # 5. Malformed and null telemetry handling
    # --------------------------------------------------------------------------
    def test_malformed_telemetry_safety(self):
        """Application must safely handle event_time=None, temperature_c='ERR', and missing keys without crashing."""
        malformed_pings = [
            {"event_time": None, "temperature_c": "ERR", "latitude": None},
            {"event_time": "2026-03-02T06:00:00", "temperature_c": "4.5", "latitude": "15.9"},
            {},  # completely empty dict
            {"event_time": "2026-03-02T06:06:00", "temperature_c": "4.6", "latitude": "15.91"},
        ]
        batch = {"batch_id": "B-MALFORMED", "route_id": "R-TEST", "device_id": "LOG-X", "formed_time": "2026-03-02T07:00:00"}
        cal = {"LOG-X": {"device_id": "LOG-X", "next_due_date": "2026-06-30", "last_calibration_date": "2026-01-01", "calibration_offset_c": "0.0"}}

        pack = build_evidence_pack(
            batch, "R-TEST", {"R-TEST": malformed_pings}, cal, {}, {}, self.thresholds
        )
        self.assertIsNotNone(pack)
        self.assertEqual(pack.batch_id, "B-MALFORMED")
        self.assertIn(pack.overall_status, ("PASS", "NEEDS_REVIEW", "FAIL"))

    # --------------------------------------------------------------------------
    # 6. check_sync_integrity with/without route_handovers
    # --------------------------------------------------------------------------
    def test_sync_integrity_optional_handovers(self):
        """check_sync_integrity functions with 1 or 2 arguments."""
        pings = [
            {"event_time": "2026-03-02T06:00:00", "sync_status": "live"},
            {"event_time": "2026-03-02T06:06:00", "sync_status": "delayed"},
        ]
        res1 = check_sync_integrity(pings)
        res2 = check_sync_integrity(pings, [])
        self.assertEqual(res1.status, res2.status)
        self.assertEqual(res1.status, "PASS")


if __name__ == "__main__":
    unittest.main()
