"""Assemble detector output directly into a zeta.KeySet."""

from zeta import KeySet

from .detectors import detect_all
from .observation import ServiceObservation
from .thresholds import SERVICE_NORMS


def observe(o: ServiceObservation, norms=SERVICE_NORMS) -> KeySet:
    """Run all detectors and return a ready-to-use zeta.KeySet. ``norms`` is the threshold table (default: the declared one)."""
    return KeySet(detect_all(o, norms))
