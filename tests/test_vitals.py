import math

import pytest

from alpha.vitals import VitalsObservation


def test_valid_vitals_construct_without_error():
    v = VitalsObservation(heart_rate=100, oxygen_saturation=98.0, respiratory_rate=20, temperature=37.0)
    assert v.heart_rate == 100


@pytest.mark.parametrize("field", ["heart_rate", "oxygen_saturation", "respiratory_rate", "temperature"])
def test_none_required_field_rejected(field):
    # Regression: previously a None required field silently propagated
    # until whichever detector touched it first raised an unlabeled
    # TypeError, discarding every other detector's result too.
    kwargs = dict(heart_rate=100, oxygen_saturation=98.0, respiratory_rate=20, temperature=37.0)
    kwargs[field] = None
    with pytest.raises(ValueError, match=field):
        VitalsObservation(**kwargs)


@pytest.mark.parametrize("field", ["heart_rate", "oxygen_saturation", "respiratory_rate", "temperature"])
def test_nan_required_field_rejected(field):
    # Regression: previously a NaN vital silently made every affected
    # detector report present=False -- indistinguishable from a
    # genuinely healthy reading (a disconnected sensor read as "fine").
    kwargs = dict(heart_rate=100, oxygen_saturation=98.0, respiratory_rate=20, temperature=37.0)
    kwargs[field] = float("nan")
    with pytest.raises(ValueError, match=field):
        VitalsObservation(**kwargs)


@pytest.mark.parametrize("field", ["heart_rate", "oxygen_saturation", "respiratory_rate", "temperature"])
def test_infinite_required_field_rejected(field):
    kwargs = dict(heart_rate=100, oxygen_saturation=98.0, respiratory_rate=20, temperature=37.0)
    kwargs[field] = math.inf
    with pytest.raises(ValueError, match=field):
        VitalsObservation(**kwargs)


def test_age_months_may_be_none():
    v = VitalsObservation(heart_rate=100, oxygen_saturation=98.0, respiratory_rate=20, temperature=37.0, age_months=None)
    assert v.age_months is None
