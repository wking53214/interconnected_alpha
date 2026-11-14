"""The pediatric-vitals domain pack: today's detectors, declared under the ``alpha.core.DomainPack`` contract.

What is declared: the age-group threshold table (``PEDIATRIC_NORMS``), as 25 bounded parameters. The three multi-vital syndrome
detectors (``septic_shock``, ``respiratory_distress``, ``hypovolemic_shock``) and ``critical_o2`` and ``hypothermia`` use fixed
absolute thresholds that live in ``detectors.py``; they are not declared as parameters yet (a later step), and the README says so.

Approval, stated plainly: nobody has approved these values. They were copied verbatim from OBSERVE's ``observe_consolidated.py`` and are not
independently clinically validated. The declaration says so in ``approved_by`` and ``justification`` instead of naming an approver, and
``approval_date`` holds the date of this declaration. Replacing that text with a real reviewer is the pack owner's decision.
"""

from typing import Tuple

from zeta import KeySet

from ...core import DomainPack, Parameter
from .detectors import ALL_DETECTORS
from .registry import observe
from .thresholds import AGE_GROUPS, PEDIATRIC_NORMS, norms_from
from .vitals import VitalsObservation

_DECLARED_ON = "2026-11-13"
_APPROVED_BY = "unapproved: copied verbatim from OBSERVE observe_consolidated.py:113-119; no clinical reviewer has approved these values"
_JUSTIFICATION = (
    "Extracted verbatim from OBSERVE's PEDIATRIC_NORMS so that the moved detectors give exactly the outputs they gave before; "
    "not independently clinically validated (see README section 4 before relying on them)."
)

# name of the table column -> (what it limits, minimum, maximum), bounds wide enough for any real reading of that quantity
_COLUMNS = {
    "hr_high": ("heart rate above which tachycardia is present (beats per minute)", 20.0, 300.0),
    "hr_low": ("heart rate below which bradycardia is present (beats per minute)", 20.0, 300.0),
    "rr_high": ("respiratory rate above which tachypnea is present (breaths per minute)", 5.0, 120.0),
    "o2_low": ("oxygen saturation below which warning_o2 is present (percent)", 50.0, 100.0),
    "temp_high": ("temperature above which fever is present (degrees Celsius)", 30.0, 45.0),
}


class PediatricVitalsPack(DomainPack):
    NAME = "pediatric_vitals"
    VERSION = "0.2.0"
    DOMAIN = "clinical"
    KEYS: Tuple[str, ...] = (
        "critical_o2",
        "warning_o2",
        "tachycardia",
        "bradycardia",
        "tachypnea",
        "fever",
        "hypothermia",
        "septic_shock",
        "respiratory_distress",
        "hypovolemic_shock",
    )

    def parameters(self) -> Tuple[Parameter, ...]:
        out = []
        for group, row in PEDIATRIC_NORMS.items():
            for column, value in row.items():
                description, minimum, maximum = _COLUMNS[column]
                out.append(Parameter(
                    name=f"{group}_{column}", value=value, minimum=minimum, maximum=maximum,
                    description=f"{group}: {description}", approved_by=_APPROVED_BY,
                    approval_date=_DECLARED_ON, justification=_JUSTIFICATION,
                ))
        return tuple(out)

    def parameter_problems(self, parameters):
        by_name = {p.name: p.value for p in parameters}
        return [f"{group}_hr_low ({by_name[f'{group}_hr_low']}) is not below {group}_hr_high ({by_name[f'{group}_hr_high']})"
                for group in AGE_GROUPS if not by_name[f"{group}_hr_low"] < by_name[f"{group}_hr_high"]]

    def _norms(self):
        """The threshold table, built once from this pack's parameters: the values the registry validated are the values used."""
        if not hasattr(self, "_norms_cache"):
            self._norms_cache = norms_from(self.parameters())
        return self._norms_cache

    def observe(self, raw: VitalsObservation) -> KeySet:
        if type(raw) is not VitalsObservation:
            raise TypeError(f"PediatricVitalsPack.observe needs exactly a VitalsObservation, got {type(raw).__name__}")
        # a fresh object: its own validation runs again, so an observation edited after construction is refused here
        raw = VitalsObservation(raw.heart_rate, raw.oxygen_saturation, raw.respiratory_rate, raw.temperature, raw.age_months)
        return observe(raw, self._norms())


__all__ = ["PediatricVitalsPack", "ALL_DETECTORS"]
