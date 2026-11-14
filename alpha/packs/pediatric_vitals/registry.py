"""Assemble detector output directly into a zeta.KeySet."""

from zeta import KeySet

from .detectors import detect_all
from .thresholds import PEDIATRIC_NORMS
from .vitals import VitalsObservation


def observe(v: VitalsObservation, norms=PEDIATRIC_NORMS) -> KeySet:
    """Run all detectors and return a ready-to-use zeta.KeySet. ``norms`` is the threshold table (default: the declared one)."""
    return KeySet(detect_all(v, norms))
