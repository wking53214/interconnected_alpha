"""Worked example: raw service readings -> alpha's service_health pack detects Keys -> zeta evaluates a Lock.

Run: PYTHONPATH=.:/path/to/interconnected_zeta python3 examples/service_degradation.py

The same wiring as examples/pediatric_discharge.py, in a different industry: nothing in alpha's core or in zeta knows which. The thresholds
are synthetic and tuned to no real service.
"""

from datetime import datetime, timedelta

from zeta import Combination, LockEvaluator, LockRegistry, LockSpec

from alpha.core import PackRegistry, pack_identity
from alpha.packs.service_health import ServiceHealthPack, ServiceObservation


def build_registry() -> LockRegistry:
    return LockRegistry([
        LockSpec(
            # Open while the service is degraded or its latency is critical: a page-the-on-call condition.
            lock_id="degradation_lock",
            required_keys=("degraded_service", "latency_critical"),
            combination=Combination.OR,
            dwell_threshold=1,
            force=True,
            lock_seconds=900,
        ),
    ])


def main() -> None:
    packs = PackRegistry()
    packs.register(ServiceHealthPack())
    print(f"pack: {pack_identity(packs.get('service_health'))}")

    evaluator = LockEvaluator(build_registry())
    t0 = datetime(2026, 11, 13, 9, 0, 0)
    timeline = [  # (minute, p95 latency ms, error rate, queue depth)
        (0, 120.0, 0.001, 5),       # healthy
        (5, 480.0, 0.08, 40),       # slow and erroring: degraded
        (10, 1500.0, 0.30, 900),    # critical latency, errors, backlog
        (25, 140.0, 0.002, 12),     # recovered
    ]
    for minute, latency, errors, depth in timeline:
        reading = ServiceObservation(latency_p95_ms=latency, error_rate=errors, queue_depth=depth, tier="interactive")
        keys = packs.observe("service_health", reading)
        print(f"\n--- T+{minute}m --- p95={latency}ms errors={errors} queue={depth} ---")
        print(f"  Keys detected: {sorted(keys.names_present()) or '(none)'}")
        for lock_id, result in evaluator.evaluate_all("checkout-service", keys, t0 + timedelta(minutes=minute)).items():
            marker = "OPEN " if result.open else "closed"
            print(f"  {lock_id:18s} {marker}  {result.reasons[0]}")


if __name__ == "__main__":
    main()
