"""The service-health thresholds, declared as parameters: the single source the detectors read.

Each tier has four limits: the latency above which ``latency_high`` is present, the latency above which ``latency_critical`` is present,
the error rate above which ``error_burst`` is present, and the queue depth above which ``queue_backlog`` is present. ``SERVICE_NORMS``
is derived from ``PARAMETERS``, so a threshold exists in exactly one place and the detectors cannot disagree with what the pack declares.

Approval, stated plainly: nobody has approved these values. They are synthetic examples that exist to exercise the pack contract and are
tuned to no real service. ``approved_by`` and ``justification`` say so, and ``approval_date`` is the date of the declaration.
"""

from typing import Dict, Tuple

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

SERVICE_NORMS: Dict[str, Dict[str, float]] = {
    tier: {column: next(p.value for p in PARAMETERS if p.name == f"{tier}_{column}") for column in row}
    for tier, row in _VALUES.items()
}
