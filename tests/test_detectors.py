import pytest

from alpha.detectors import (
    ALL_DETECTORS,
    bradycardia,
    critical_o2,
    detect_all,
    fever,
    hypothermia,
    hypovolemic_shock,
    respiratory_distress,
    septic_shock,
    tachycardia,
    tachypnea,
    warning_o2,
)
from alpha.vitals import VitalsObservation


def normal_child(**overrides):
    """Baseline: normal vitals for a 4-year-old (age_group='child',
    thresholds hr_high=130, hr_low=100, rr_high=35, o2_low=92, temp_high=39.5)."""
    defaults = dict(heart_rate=110, oxygen_saturation=98.0, respiratory_rate=20, temperature=37.0, age_months=48)
    defaults.update(overrides)
    return VitalsObservation(**defaults)


# --- critical_o2 / warning_o2 ---

def test_critical_o2_fires_below_88():
    v = normal_child(oxygen_saturation=87.9)
    assert critical_o2(v).present is True


def test_critical_o2_does_not_fire_at_exactly_88():
    v = normal_child(oxygen_saturation=88.0)
    assert critical_o2(v).present is False  # source uses strict '<'


def test_warning_o2_fires_between_88_and_age_threshold():
    # child o2_low = 92
    v = normal_child(oxygen_saturation=90.0)
    assert critical_o2(v).present is False
    assert warning_o2(v).present is True


def test_warning_o2_mutually_exclusive_with_critical_o2():
    v = normal_child(oxygen_saturation=80.0)  # well below both thresholds
    assert critical_o2(v).present is True
    assert warning_o2(v).present is False, "warning_o2 must not fire when critical_o2 already does"


def test_warning_o2_does_not_fire_above_threshold():
    v = normal_child(oxygen_saturation=95.0)
    assert warning_o2(v).present is False


@pytest.mark.parametrize("age_months,o2_low", [
    (1, 90), (6, 90), (24, 91), (48, 92), (None, 91),
])
def test_warning_o2_uses_correct_age_adjusted_threshold(age_months, o2_low):
    v = normal_child(age_months=age_months, oxygen_saturation=o2_low - 0.5)
    assert warning_o2(v).present is True
    v2 = normal_child(age_months=age_months, oxygen_saturation=o2_low + 1)
    assert warning_o2(v2).present is False


# --- tachycardia / bradycardia ---

def test_tachycardia_fires_above_age_adjusted_threshold():
    v = normal_child(heart_rate=131)  # child hr_high=130
    assert tachycardia(v).present is True


def test_tachycardia_does_not_fire_at_threshold():
    v = normal_child(heart_rate=130)
    assert tachycardia(v).present is False  # strict '>'


def test_bradycardia_fires_below_age_adjusted_threshold():
    v = normal_child(heart_rate=99)  # child hr_low=100
    assert bradycardia(v).present is True


def test_bradycardia_does_not_fire_at_threshold():
    v = normal_child(heart_rate=100)
    assert bradycardia(v).present is False


# --- tachypnea ---

def test_tachypnea_fires_above_age_adjusted_threshold():
    v = normal_child(respiratory_rate=36)  # child rr_high=35
    assert tachypnea(v).present is True


def test_tachypnea_does_not_fire_at_threshold():
    v = normal_child(respiratory_rate=35)
    assert tachypnea(v).present is False


# --- fever / hypothermia ---

def test_fever_fires_above_age_adjusted_threshold():
    v = normal_child(temperature=39.6)  # child temp_high=39.5
    assert fever(v).present is True


def test_fever_does_not_fire_at_threshold():
    v = normal_child(temperature=39.5)
    assert fever(v).present is False


def test_hypothermia_fires_below_35():
    v = normal_child(temperature=34.9)
    assert hypothermia(v).present is True


def test_hypothermia_does_not_fire_at_35():
    v = normal_child(temperature=35.0)
    assert hypothermia(v).present is False


# --- Named syndromes: fixed thresholds, NOT age-adjusted ---

def test_septic_shock_requires_all_four_conditions():
    v = VitalsObservation(heart_rate=145, oxygen_saturation=90.0, respiratory_rate=36, temperature=39.0)
    assert septic_shock(v).present is True


@pytest.mark.parametrize("field,value", [
    ("oxygen_saturation", 93.0),   # not < 92
    ("heart_rate", 130),           # not > 140
    ("respiratory_rate", 30),      # not > 35
    ("temperature", 38.0),         # not > 38.5
])
def test_septic_shock_absent_if_any_condition_fails(field, value):
    base = dict(heart_rate=145, oxygen_saturation=90.0, respiratory_rate=36, temperature=39.0)
    base[field] = value
    v = VitalsObservation(**base)
    assert septic_shock(v).present is False


def test_septic_shock_ignores_age_months():
    # Fixed absolute thresholds -- same vitals, different ages, same result.
    vitals_kwargs = dict(heart_rate=145, oxygen_saturation=90.0, respiratory_rate=36, temperature=39.0)
    v_infant = VitalsObservation(age_months=6, **vitals_kwargs)
    v_child = VitalsObservation(age_months=48, **vitals_kwargs)
    assert septic_shock(v_infant).present is True
    assert septic_shock(v_child).present is True


def test_respiratory_distress_requires_both_conditions():
    v = VitalsObservation(heart_rate=110, oxygen_saturation=89.0, respiratory_rate=46, temperature=37.0)
    assert respiratory_distress(v).present is True

    v_partial = VitalsObservation(heart_rate=110, oxygen_saturation=91.0, respiratory_rate=46, temperature=37.0)
    assert respiratory_distress(v_partial).present is False


def test_hypovolemic_shock_requires_both_conditions():
    v = VitalsObservation(heart_rate=155, oxygen_saturation=87.0, respiratory_rate=20, temperature=37.0)
    assert hypovolemic_shock(v).present is True

    v_partial = VitalsObservation(heart_rate=155, oxygen_saturation=90.0, respiratory_rate=20, temperature=37.0)
    assert hypovolemic_shock(v_partial).present is False


# --- detect_all ---

def test_detect_all_returns_one_key_per_detector():
    v = normal_child()
    keys = detect_all(v)
    assert len(keys) == len(ALL_DETECTORS)


def test_detect_all_names_are_unique():
    v = normal_child()
    names = [k.name for k in detect_all(v)]
    assert len(names) == len(set(names))


def test_detect_all_on_normal_vitals_has_no_present_keys():
    v = normal_child()
    keys = detect_all(v)
    assert all(not k.present for k in keys), [k.name for k in keys if k.present]


def test_detect_all_raises_on_duplicate_key_names():
    # Regression guard: a copy-paste detector bug that reused an existing
    # Key name would otherwise silently lose one Key when fed into
    # zeta.KeySet (which de-dupes by name with no warning). Verify the
    # guard actually fires, using a temporarily-patched detector list
    # rather than requiring a real bug to exist in ALL_DETECTORS.
    import alpha.detectors as detectors_module

    original = detectors_module.ALL_DETECTORS
    try:
        detectors_module.ALL_DETECTORS = (detectors_module.critical_o2, detectors_module.critical_o2)
        with pytest.raises(AssertionError, match="duplicate"):
            detectors_module.detect_all(normal_child())
    finally:
        detectors_module.ALL_DETECTORS = original


def test_all_syndrome_keys_have_confidence_one_by_design():
    # Documents the intentional design choice (see detectors.py
    # docstring): these are deterministic boolean checks, not
    # probabilistic detections, so confidence is always the zeta.Key
    # default of 1.0 -- never populated from the source's severity
    # weights or fusion-level confidence values.
    v = VitalsObservation(heart_rate=145, oxygen_saturation=90.0, respiratory_rate=36, temperature=39.6, age_months=14)
    keys = detect_all(v)
    assert all(k.confidence == 1.0 for k in keys)
