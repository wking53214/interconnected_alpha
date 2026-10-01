"""alpha: detects named Keys in raw pediatric vitals.

Extracted from two scoring methods in the original private implementation
that computed named clinical signals inline as
part of a single accumulated risk score. This module pulls those named
checks out as standalone, independently testable detectors that each
produce a `zeta.Key` -- the first-class unit `zeta`'s Locks combine.

See `alpha/detectors.py` for the full extraction provenance, including
what is faithfully preserved (age-adjustment asymmetry, elif-exclusivity
between critical_o2/warning_o2) and what is explicitly out of scope
(score-modulation logic that doesn't fit the Key present/absent model).
"""

from .vitals import VitalsObservation
from .thresholds import PEDIATRIC_NORMS, get_age_group
from .detectors import ALL_DETECTORS, detect_all
from .registry import observe

__all__ = [
    "VitalsObservation",
    "PEDIATRIC_NORMS",
    "get_age_group",
    "ALL_DETECTORS",
    "detect_all",
    "observe",
]

__version__ = "0.1.0"
