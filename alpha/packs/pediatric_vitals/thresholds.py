"""Age-adjusted pediatric vital-sign thresholds.

Extracted verbatim from observe_consolidated.py:113-119 (PEDIATRIC_NORMS)
and observe_consolidated.py:247-257 (get_age_group). These are the exact
source values, not re-derived or approximated. These values are copied from
the source and are not independently clinically validated; see README
section 4 before relying on them.
"""

from types import MappingProxyType
from typing import Any, Iterable, Mapping, Optional

AGE_GROUPS = ("neonatal", "infant", "toddler", "child", "generic")
NORM_COLUMNS = ("hr_high", "hr_low", "rr_high", "o2_low", "temp_high")

_RAW = {
    "neonatal": {"hr_high": 160, "hr_low": 80, "rr_high": 50, "o2_low": 90, "temp_high": 38.5},
    "infant":   {"hr_high": 150, "hr_low": 90, "rr_high": 45, "o2_low": 90, "temp_high": 39.0},
    "toddler":  {"hr_high": 140, "hr_low": 95, "rr_high": 40, "o2_low": 91, "temp_high": 39.0},
    "child":    {"hr_high": 130, "hr_low": 100, "rr_high": 35, "o2_low": 92, "temp_high": 39.5},
    "generic":  {"hr_high": 140, "hr_low": 95, "rr_high": 40, "o2_low": 91, "temp_high": 39.0},
}

# Read-only at both levels: a threshold the pack declared cannot be edited in place behind the registry. The detectors read the table
# the pack builds from its registered parameters (see ``norms_from``); this one is the default and the source of the declaration.
PEDIATRIC_NORMS: Mapping[str, Mapping[str, float]] = MappingProxyType({group: MappingProxyType(dict(row)) for group, row in _RAW.items()})


def norms_from(parameters: Iterable[Any]) -> Mapping[str, Mapping[str, float]]:
    """The detectors' table, read from a pack's parameters (names ``<group>_<column>``). A missing parameter is an error, not a default."""
    by_name = {p.name: p.value for p in parameters}
    return MappingProxyType({group: MappingProxyType({column: by_name[f"{group}_{column}"] for column in NORM_COLUMNS})
                             for group in AGE_GROUPS})


def get_age_group(age_months: Optional[int]) -> str:
    """Map age in months to a clinical age group. None -> 'generic'."""
    if age_months is None:
        return "generic"
    if age_months < 3:
        return "neonatal"
    if age_months < 12:
        return "infant"
    if age_months < 36:
        return "toddler"
    return "child"
