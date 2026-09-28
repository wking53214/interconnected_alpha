from alpha.registry import observe
from alpha.vitals import VitalsObservation


def test_observe_returns_keyset_with_expected_present_names():
    # child (age_months=48) thresholds: hr_high=130, temp_high=39.5
    v = VitalsObservation(heart_rate=145, oxygen_saturation=90.0, respiratory_rate=36, temperature=39.6, age_months=48)
    ks = observe(v)
    assert ks.is_present("septic_shock") is True
    assert ks.is_present("tachycardia") is True
    assert ks.is_present("fever") is True


def test_observe_normal_vitals_has_no_present_keys():
    v = VitalsObservation(heart_rate=100, oxygen_saturation=98.0, respiratory_rate=18, temperature=37.0, age_months=48)
    ks = observe(v)
    assert ks.names_present() == set()


def test_observe_keyset_feeds_directly_into_zeta_lock_evaluation():
    # Integration check: alpha's output is directly consumable by zeta,
    # with no adapter layer in between.
    from datetime import datetime
    from zeta import Combination, LockEvaluator, LockRegistry, LockSpec

    registry = LockRegistry([
        LockSpec(
            lock_id="sepsis_lock",
            required_keys=("septic_shock", "respiratory_distress", "hypovolemic_shock"),
            combination=Combination.OR,
            force=True,
        ),
    ])
    evaluator = LockEvaluator(registry)

    v = VitalsObservation(heart_rate=145, oxygen_saturation=90.0, respiratory_rate=36, temperature=39.0, age_months=48)
    keys = observe(v)

    result = evaluator.evaluate("patient1", keys, "sepsis_lock", datetime(2026, 1, 1))
    assert result.open is True
    assert result.forced is True
