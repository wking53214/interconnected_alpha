"""ServiceObservation: the raw reading this pack consumes, validated where raw data enters.

A reading of a running service over one window: the 95th-percentile latency in milliseconds, the error rate as a fraction of requests,
the depth of its work queue, and the tier the service runs in (``interactive`` or ``batch``), which sets the thresholds. Each number must be
an exact ``int`` or ``float`` (never a ``bool``, a string or ``None``), finite, and within its physical range; the tier must be exactly one
of the known strings. A bad reading is refused here instead of making every detector quietly report "absent".
"""

import math
from dataclasses import dataclass

TIERS = ("interactive", "batch")


def _number(name: str, value: object) -> float:
    if type(value) not in (int, float):
        raise TypeError(f"ServiceObservation.{name} must be an exact int or float, got {type(value).__name__}")
    if not math.isfinite(value):
        raise ValueError(f"ServiceObservation.{name} must be finite, got {value!r}")
    return value


@dataclass(frozen=True)
class ServiceObservation:
    latency_p95_ms: float
    error_rate: float
    queue_depth: float
    tier: str = "interactive"

    def __post_init__(self) -> None:
        latency = _number("latency_p95_ms", self.latency_p95_ms)
        rate = _number("error_rate", self.error_rate)
        depth = _number("queue_depth", self.queue_depth)
        if latency < 0:
            raise ValueError(f"ServiceObservation.latency_p95_ms cannot be negative, got {latency!r}")
        if not 0.0 <= rate <= 1.0:
            raise ValueError(f"ServiceObservation.error_rate is a fraction between 0 and 1, got {rate!r}")
        if depth < 0:
            raise ValueError(f"ServiceObservation.queue_depth cannot be negative, got {depth!r}")
        if type(self.tier) is not str:
            raise TypeError(f"ServiceObservation.tier must be an exact str, got {type(self.tier).__name__}")
        if self.tier not in TIERS:
            raise ValueError(f"ServiceObservation.tier must be one of {TIERS}, got {self.tier!r}")
