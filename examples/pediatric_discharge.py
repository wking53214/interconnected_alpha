"""Worked example: raw vitals -> alpha detects Keys -> zeta evaluates Locks.

Run: PYTHONPATH=.:/path/to/interconnected_zeta python3 examples/pediatric_discharge.py

This is the same clinical scenario as interconnected_zeta's own example,
but here the Keys come from alpha's detectors instead of being hand-built
-- showing the two repos wired together end to end.
"""

from datetime import datetime, timedelta

from zeta import Combination, LockEvaluator, LockRegistry, LockSpec

from alpha import VitalsObservation, observe


def build_registry() -> LockRegistry:
    return LockRegistry([
        LockSpec(
            lock_id="sepsis_lock",
            required_keys=("septic_shock", "respiratory_distress", "hypovolemic_shock"),
            combination=Combination.OR,
            dwell_threshold=1,
            force=True,
            lock_seconds=3600,
        ),
        LockSpec(
            # Named for what the lock DETECTS, not what it authorizes:
            # discharge is only safe while this lock is CLOSED (no
            # abnormal vitals key present). An open sepsis_lock or
            # abnormal_vitals_lock both mean "not dischargeable yet."
            lock_id="abnormal_vitals_lock",
            required_keys=("tachycardia", "fever", "tachypnea"),
            combination=Combination.OR,
            dwell_threshold=1,
            force=True,  # any abnormal reading immediately blocks discharge, no debounce
        ),
    ])


def main():
    registry = build_registry()
    evaluator = LockEvaluator(registry)
    t0 = datetime(2026, 10, 1, 8, 0, 0)
    patient = "patient_14mo_001"

    # (hour, HR, O2, RR, temp, age_months)
    timeline = [
        (0, 148, 90.0, 36, 39.6, 14),   # admission: multiple abnormal signs, sepsis pattern present
        (14, 118, 96.0, 26, 38.0, 14),  # improving but still tachypneic-adjacent, fever gone
        (26, 96, 98.0, 22, 37.0, 14),   # normal vitals
    ]

    for hour, hr, o2, rr, temp, age in timeline:
        ts = t0 + timedelta(hours=hour)
        vitals = VitalsObservation(heart_rate=hr, oxygen_saturation=o2, respiratory_rate=rr,
                                    temperature=temp, age_months=age)
        keys = observe(vitals)

        print(f"\n--- T+{hour}h --- HR={hr} O2={o2}% RR={rr} temp={temp} ---")
        print(f"  Keys detected: {sorted(keys.names_present()) or '(none)'}")

        results = evaluator.evaluate_all(patient, keys, ts)
        for lock_id, result in results.items():
            marker = "OPEN " if result.open else "closed"
            forced = " [FORCED]" if result.forced else ""
            print(f"  {lock_id:16s} {marker}{forced}  {result.reasons[0]}")


if __name__ == "__main__":
    main()
