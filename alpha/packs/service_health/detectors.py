"""Service-health detectors: named, single-purpose checks against a ServiceObservation, each producing a ``zeta.Key``.

Five Keys. Four are single readings against the tier's declared threshold (``latency_high``, ``latency_critical``, ``error_burst``,
``queue_backlog``); ``degraded_service`` is the named syndrome of high latency together with an error burst. Critical latency is also
high latency, so both Keys are present then. Every Key carries confidence 1.0: each is a deterministic threshold comparison with no
detection uncertainty. Thresholds come from ``thresholds.SERVICE_NORMS``, which is derived from the declared parameters.
"""

from zeta import Key

from .observation import ServiceObservation
from .thresholds import SERVICE_NORMS


def latency_high(o: ServiceObservation) -> Key:
    limit = SERVICE_NORMS[o.tier]["latency_high"]
    return Key(name="latency_high", present=o.latency_p95_ms > limit,
               reason=f"p95 latency {o.latency_p95_ms} ms vs threshold {limit} ms ({o.tier})")


def latency_critical(o: ServiceObservation) -> Key:
    limit = SERVICE_NORMS[o.tier]["latency_critical"]
    return Key(name="latency_critical", present=o.latency_p95_ms > limit,
               reason=f"p95 latency {o.latency_p95_ms} ms vs critical threshold {limit} ms ({o.tier})")


def error_burst(o: ServiceObservation) -> Key:
    limit = SERVICE_NORMS[o.tier]["error_high"]
    return Key(name="error_burst", present=o.error_rate > limit,
               reason=f"error rate {o.error_rate} vs threshold {limit} ({o.tier})")


def queue_backlog(o: ServiceObservation) -> Key:
    limit = SERVICE_NORMS[o.tier]["queue_high"]
    return Key(name="queue_backlog", present=o.queue_depth > limit,
               reason=f"queue depth {o.queue_depth} vs threshold {limit} ({o.tier})")


def degraded_service(o: ServiceObservation) -> Key:
    present = latency_high(o).present and error_burst(o).present
    return Key(name="degraded_service", present=present,
               reason="high p95 latency and an error burst together" if present else "not both high latency and an error burst")


ALL_DETECTORS = (latency_high, latency_critical, error_burst, queue_backlog, degraded_service)


def detect_all(o: ServiceObservation):
    """Run every detector and return the Keys, refusing a duplicate name (zeta's KeySet would silently drop one)."""
    keys = [detector(o) for detector in ALL_DETECTORS]
    names = [k.name for k in keys]
    if len(names) != len(set(names)):
        raise AssertionError(f"detect_all() produced duplicate Key names: {sorted({n for n in names if names.count(n) > 1})}")
    return keys
