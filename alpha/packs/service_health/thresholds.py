"""The service-health thresholds, declared as parameters: the single source the detectors read.

Each tier has four limits: the latency above which ``latency_high`` is present, the latency above which ``latency_critical`` is present,
the error rate above which ``error_burst`` is present, and the queue depth above which ``queue_backlog`` is present. ``SERVICE_NORMS``
is derived from ``PARAMETERS``, so a threshold exists in exactly one place and the detectors cannot disagree with what the pack declares.

Approval, stated plainly: nobody has approved these values. They are synthetic examples that exist to exercise the pack contract and are
tuned to no real service. ``approved_by`` and ``justification`` say so, and ``approval_date`` is the date of the declaration.
"""

from types import MappingProxyType
from typing import Any, Iterable, Mapping, Tuple

from ...core import Parameter

_DECLARED_ON = "2026-11-13"
_APPROVED_BY = "unapproved: synthetic example values for demonstrating the pack contract; nobody has approved them for any real service"
_JUSTIFICATION = "Synthetic values chosen to exercise the contract and the detectors; not derived from any real service's behaviour or targets."

# column -> (what it limits, minimum, maximum), then per tier the value
_COLUMNS = {
    "latency_high": ("p95 latency above which latency_high is present (milliseconds)", 0.0, 3_600_000.0),
    "latency_critical": ("p95 latency above which latency_critical is present (milliseconds)", 0.0, 3_600_000.0),
    "error_high": ("error rate above which error_burst is present (fraction of requests)", 0.0, 1.0),
    "queue_high": ("queue depth above which queue_backlog is present (items)", 0.0, 100_000_000.0),
}
_VALUES = {
    "interactive": {"latency_high": 300.0, "latency_critical": 1000.0, "error_high": 0.02, "queue_high": 100.0},
    "batch": {"latency_high": 5000.0, "latency_critical": 30000.0, "error_high": 0.05, "queue_high": 10000.0},
}

PARAMETERS: Tuple[Parameter, ...] = tuple(
    Parameter(
        name=f"{tier}_{column}", value=value, minimum=_COLUMNS[column][1], maximum=_COLUMNS[column][2],
        description=f"{tier}: {_COLUMNS[column][0]}", approved_by=_APPROVED_BY,
        approval_date=_DECLARED_ON, justification=_JUSTIFICATION,
    )
    for tier, row in _VALUES.items()
    for column, value in row.items()
)

TIER_NAMES = tuple(_VALUES)
NORM_COLUMNS = tuple(_COLUMNS)


def norms_from(parameters: Iterable[Any]) -> Mapping[str, Mapping[str, float]]:
    """The detectors' table, read from a pack's parameters (names ``<tier>_<column>``), read-only. A missing parameter is an error."""
    by_name = {p.name: p.value for p in parameters}
    return MappingProxyType({tier: MappingProxyType({column: by_name[f"{tier}_{column}"] for column in NORM_COLUMNS})
                             for tier in TIER_NAMES})


# Derived from PARAMETERS and read-only: the default table, and the same values the pack declares.
SERVICE_NORMS: Mapping[str, Mapping[str, float]] = norms_from(PARAMETERS)
