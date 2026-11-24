"""Age-adjusted pediatric vital-sign thresholds.

Heart rate, respiratory rate and newborn fever limits were re-derived on
2026-11-23 from published references and are PROVISIONAL PROXIES, NOT
CLINICALLY VALIDATED (not independently clinically validated). Before that the table was a verbatim copy of OBSERVE's
PEDIATRIC_NORMS (observe_consolidated.py:113-119), whose low heart-rate limit
rose with age (80, 90, 95, 100), the wrong way round. The oxygen limits and the
other fever limits were reviewed and left as they were. The old single "child"
group (3 to 18 years) was split on 2026-11-23 into preschool, school and
adolescent, as in OBSERVE. See README section 4.

Sources: Fleming et al., Lancet 2011;377:1011 (web appendix, tables 4-5:
centiles of heart and respiratory rate in healthy children); Goldstein et al.,
Pediatr Crit Care Med 2005;6:2 (consensus); AAP, Pediatrics 2021;148:e2021052228
(fever is 38.0 C or above under 2 months; the detectors use ">" so the limit is
37.9). Method: a limit is placed so a healthy child anywhere in the age group is
flagged by rate alone about 1% of the time or less. That costs sensitivity at the
young end of a group. Two adolescent limits are looser than the evidence (heart
rate high 115, published 99th centile 108; respiratory rate high 26, published
23) because OBSERVE's faulted-channel placeholders (HR 110, RR 25) must sit
inside every window there; they are kept equal here so the two systems agree.
"""

from types import MappingProxyType
from typing import Any, Iterable, Mapping, Optional

AGE_GROUPS = ("neonatal", "infant", "toddler", "preschool", "school", "adolescent", "generic")
NORM_COLUMNS = ("hr_high", "hr_low", "rr_high", "o2_low", "temp_high")

_RAW = {
    "neonatal": {"hr_high": 180, "hr_low": 90, "rr_high": 60, "o2_low": 90, "temp_high": 37.9},
    "infant":   {"hr_high": 175, "hr_low": 90, "rr_high": 60, "o2_low": 90, "temp_high": 39.0},
    "toddler":  {"hr_high": 150, "hr_low": 75, "rr_high": 45, "o2_low": 91, "temp_high": 39.0},
    "preschool": {"hr_high": 135, "hr_low": 65, "rr_high": 33, "o2_low": 92, "temp_high": 39.5},   # 3 to <6 years
    "school":   {"hr_high": 125, "hr_low": 50, "rr_high": 27, "o2_low": 92, "temp_high": 39.5},    # 6 to <12 years
    "adolescent": {"hr_high": 115, "hr_low": 45, "rr_high": 26, "o2_low": 92, "temp_high": 39.5},  # 12 years and up
    "generic":  {"hr_high": 160, "hr_low": 50, "rr_high": 40, "o2_low": 91, "temp_high": 39.0},
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
    if age_months < 72:
        return "preschool"
    if age_months < 144:
        return "school"
    return "adolescent"
