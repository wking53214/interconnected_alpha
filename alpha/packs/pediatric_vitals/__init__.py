"""pediatric_vitals: a domain pack that detects named Keys in raw pediatric vitals.

Extracted from two scoring methods in OBSERVE's RiskAdapters
(observe_consolidated.py) that computed named clinical signals inline as
part of a single accumulated risk score. This module pulls those named
checks out as standalone, independently testable detectors that each
produce a `zeta.Key` -- the first-class unit `zeta`'s Locks combine.

See `alpha/packs/pediatric_vitals/detectors.py` for the full extraction provenance, including
what is faithfully preserved (age-adjustment asymmetry, elif-exclusivity
between critical_o2/warning_o2) and what is explicitly out of scope
(score-modulation logic that doesn't fit the Key present/absent model).
"""

from .detectors import ALL_DETECTORS, detect_all
from .pack import PediatricVitalsPack
from .registry import observe
from .thresholds import PEDIATRIC_NORMS, get_age_group
from .vitals import VitalsObservation

__all__ = [
    "ALL_DETECTORS",
    "PEDIATRIC_NORMS",
    "PediatricVitalsPack",
    "VitalsObservation",
    "detect_all",
    "get_age_group",
    "observe",
]
