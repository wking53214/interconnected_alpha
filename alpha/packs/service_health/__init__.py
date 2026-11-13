"""service_health: a domain pack that detects named Keys in raw readings of a running service.

The second pack, written to show that alpha's core is tied to no one domain. Its values are synthetic and tuned to no real service.
"""

from .detectors import ALL_DETECTORS, detect_all
from .observation import TIERS, ServiceObservation
from .pack import ServiceHealthPack
from .registry import observe
from .thresholds import PARAMETERS, SERVICE_NORMS

__all__ = [
    "ALL_DETECTORS",
    "PARAMETERS",
    "SERVICE_NORMS",
    "TIERS",
    "ServiceHealthPack",
    "ServiceObservation",
    "detect_all",
    "observe",
]
