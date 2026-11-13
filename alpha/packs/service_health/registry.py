"""Assemble detector output directly into a zeta.KeySet."""

from zeta import KeySet

from .detectors import detect_all
from .observation import ServiceObservation


def observe(o: ServiceObservation) -> KeySet:
    """Run all detectors and return a ready-to-use zeta.KeySet."""
    return KeySet(detect_all(o))
