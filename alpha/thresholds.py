"""Age-adjusted pediatric vital-sign thresholds.

PEDIATRIC_NORMS and get_age_group are extracted verbatim from the original
private implementation. These are the exact
source values, not re-derived or approximated.
"""

from typing import Dict, Optional

PEDIATRIC_NORMS: Dict[str, Dict[str, float]] = {
    "neonatal": {"hr_high": 160, "hr_low": 80, "rr_high": 50, "o2_low": 90, "temp_high": 38.5},
    "infant":   {"hr_high": 150, "hr_low": 90, "rr_high": 45, "o2_low": 90, "temp_high": 39.0},
    "toddler":  {"hr_high": 140, "hr_low": 95, "rr_high": 40, "o2_low": 91, "temp_high": 39.0},
    "child":    {"hr_high": 130, "hr_low": 100, "rr_high": 35, "o2_low": 92, "temp_high": 39.5},
    "generic":  {"hr_high": 140, "hr_low": 95, "rr_high": 40, "o2_low": 91, "temp_high": 39.0},
}


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
