import pytest

from alpha.thresholds import PEDIATRIC_NORMS, get_age_group


@pytest.mark.parametrize("age_months,expected", [
    (0, "neonatal"),
    (2, "neonatal"),
    (3, "infant"),
    (11, "infant"),
    (12, "toddler"),
    (35, "toddler"),
    (36, "child"),
    (200, "child"),
    (None, "generic"),
])
def test_get_age_group_boundaries(age_months, expected):
    assert get_age_group(age_months) == expected


def test_all_age_groups_have_required_fields():
    required = {"hr_high", "hr_low", "rr_high", "o2_low", "temp_high"}
    for group, values in PEDIATRIC_NORMS.items():
        assert required.issubset(values.keys()), f"{group} missing fields"


def test_o2_low_always_above_critical_threshold_of_88():
    # This invariant is why warning_o2 must explicitly exclude the
    # critical_o2 case (see detectors.py docstring) -- if any age group's
    # o2_low dropped to <= 88, that reasoning would need revisiting.
    for group, values in PEDIATRIC_NORMS.items():
        assert values["o2_low"] > 88.0, f"{group} o2_low breaks the critical/warning exclusivity assumption"


def test_get_age_group_never_returns_a_key_missing_from_pediatric_norms():
    # Regression guard (adversarial review): get_age_group()'s return
    # values and PEDIATRIC_NORMS's keys are two independently-maintained
    # sources of truth. If either changes without the other, detectors.py's
    # PEDIATRIC_NORMS[get_age_group(...)] lookups would raise a bare
    # KeyError with no context. This pins every representative age band
    # (plus None) to a real PEDIATRIC_NORMS key.
    representative_ages = [0, 2, 3, 11, 12, 35, 36, 200, None]
    produced_groups = {get_age_group(a) for a in representative_ages}
    assert produced_groups <= set(PEDIATRIC_NORMS.keys())
