"""VitalsObservation: the minimal raw-input shape alpha's detectors consume.

Not a copy of OBSERVE's full VitalsSnapshot (which also carries patient_id,
timestamp, and an open-ended context dict serving many purposes unrelated
to detection) -- just the four raw vital signs plus age_months, the only
context field the extracted detectors actually read.

Validates required fields at construction (adversarial review found that,
without this, a NaN vital silently made every affected detector report
present=False -- indistinguishable from a genuinely healthy reading -- and
a None vital crashed detect_all() with an unlabeled TypeError from
whichever detector happened to touch it first, discarding results from
unrelated detectors too). Failing fast here, at the one place raw data
enters the module, is more useful than either silent failure.
"""

import math
from dataclasses import dataclass
from typing import Optional

_REQUIRED_FIELDS = ("heart_rate", "oxygen_saturation", "respiratory_rate", "temperature")


@dataclass(frozen=True)
class VitalsObservation:
    heart_rate: float
    oxygen_saturation: float
    respiratory_rate: float
    temperature: float
    age_months: Optional[int] = None

    def __post_init__(self) -> None:
        for field_name in _REQUIRED_FIELDS:
            value = getattr(self, field_name)
            if value is None:
                raise ValueError(f"VitalsObservation.{field_name} is required and cannot be None")
            if not math.isfinite(value):
                raise ValueError(f"VitalsObservation.{field_name} must be finite, got {value!r}")
