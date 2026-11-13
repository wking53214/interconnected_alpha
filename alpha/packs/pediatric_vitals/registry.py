"""Assemble detector output directly into a zeta.KeySet."""

from zeta import KeySet

from .detectors import detect_all
from .vitals import VitalsObservation


def observe(v: VitalsObservation) -> KeySet:
    """Run all detectors and return a ready-to-use zeta.KeySet."""
    return KeySet(detect_all(v))
