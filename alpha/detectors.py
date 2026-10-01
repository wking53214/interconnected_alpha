"""Key detectors: named, single-purpose pattern checks against a VitalsObservation.

Each function here is extracted from a scoring branch that, in the
original private implementation (referred to below as the source),
existed only as one `if`/`elif` clause inline in a larger score
accumulator (two separate scoring methods there) -- never as a standalone,
independently testable,
reusable unit. Extracting them is what makes them usable as named
`zeta.Key` inputs to a Lock, which needs named Keys to combine under
AND/OR/N-of-M, not one opaque accumulated score.

Two groups, extracted from two different source methods with two
different threshold styles -- preserved faithfully, not harmonized:

  - Single-vital, AGE-ADJUSTED detectors, from the first of the two
    source methods: critical_o2, warning_o2,
    tachycardia, bradycardia, tachypnea, fever, hypothermia.

  - Multi-vital, named-syndrome detectors using FIXED absolute
    thresholds (NOT age-adjusted), from the second of the two source
    methods: septic_shock,
    respiratory_distress, hypovolemic_shock. The source does not
    age-adjust these three checks; that asymmetry is reproduced here
    exactly, not smoothed over.

Explicitly OUT OF SCOPE (not extracted, and not silently approximated):
  - The base risk score and benign-pattern suppressions in the second
    source method are
    score-accumulation and score-modulation logic ("reduce the score by
    N because of context Y"), not "is this named condition present"
    checks. They don't fit the Key model and are left to whatever
    governance layer wants that specific scoring behavior.
  - The per-syndrome SEVERITY WEIGHTS the source adds on top of each
    boolean match -- score += 0.40 for septic_shock, += 0.35 for
    respiratory_distress, += 0.35 for hypovolemic_shock
    -- are also dropped. An
    earlier version of this docstring didn't mention this; adversarial
    review caught the omission. These weights live INSIDE the part of
    the source claimed as faithfully extracted, so leaving them out silently
    would have been a real misrepresentation, not a minor gap.

On Key.confidence: every detector here always produces confidence=1.0
(zeta.Key's default). This is intentional, not a placeholder -- every
check above is a deterministic threshold or boolean-AND comparison on
the given numbers, with no probabilistic uncertainty in the DETECTION
itself. The source's severity weights above are a different concept
(how much a pattern should count toward an aggregate risk score, a
governance/prioritization question) than detection confidence (how sure
are we this pattern is present, an observation question), and conflating
the two by stuffing severity into `confidence=` would misuse the field.
Neither the first source method's data-completeness confidence nor the
second source method's alert-context confidence is
reproduced here either -- both are properties of the SOURCE's overall
risk-fusion output, not of any single named condition, and have no home
in a per-Key model. A caller that needs severity weighting or
data-completeness confidence needs it from a different layer, not from
these detectors.
"""

from zeta import Key

from .thresholds import PEDIATRIC_NORMS, get_age_group
from .vitals import VitalsObservation


# --- Single-vital, age-adjusted detectors ---
# (extracted from the first of the two source methods)

def critical_o2(v: VitalsObservation) -> Key:
    present = v.oxygen_saturation < 88.0
    return Key(
        name="critical_o2",
        present=present,
        reason=f"O2 {v.oxygen_saturation}% {'< 88% (critical)' if present else '>= 88%'}",
    )


def warning_o2(v: VitalsObservation) -> Key:
    # Source note: the warning_o2 check is an
    # `elif` under the critical_o2 check. This is NOT a vacuous ordering: every
    # age-adjusted o2_low threshold (90/90/91/92/91) is above 88, so
    # "O2 < 88" always also satisfies "O2 < o2_low". Without excluding
    # the critical case explicitly, warning_o2 would also fire whenever
    # critical_o2 does. Reproduced here as an explicit exclusion so the
    # two remain mutually exclusive exactly as in the source.
    thresh = PEDIATRIC_NORMS[get_age_group(v.age_months)]["o2_low"]
    present = (not critical_o2(v).present) and v.oxygen_saturation < thresh
    return Key(
        name="warning_o2",
        present=present,
        reason=f"O2 {v.oxygen_saturation}% vs age-adjusted threshold {thresh}%",
    )


def tachycardia(v: VitalsObservation) -> Key:
    thresh = PEDIATRIC_NORMS[get_age_group(v.age_months)]["hr_high"]
    present = v.heart_rate > thresh
    return Key(name="tachycardia", present=present, reason=f"HR {v.heart_rate} vs threshold {thresh}")


def bradycardia(v: VitalsObservation) -> Key:
    thresh = PEDIATRIC_NORMS[get_age_group(v.age_months)]["hr_low"]
    present = v.heart_rate < thresh
    return Key(name="bradycardia", present=present, reason=f"HR {v.heart_rate} vs threshold {thresh}")


def tachypnea(v: VitalsObservation) -> Key:
    thresh = PEDIATRIC_NORMS[get_age_group(v.age_months)]["rr_high"]
    present = v.respiratory_rate > thresh
    return Key(name="tachypnea", present=present, reason=f"RR {v.respiratory_rate} vs threshold {thresh}")


def fever(v: VitalsObservation) -> Key:
    thresh = PEDIATRIC_NORMS[get_age_group(v.age_months)]["temp_high"]
    present = v.temperature > thresh
    return Key(name="fever", present=present, reason=f"Temp {v.temperature} vs threshold {thresh}")


def hypothermia(v: VitalsObservation) -> Key:
    present = v.temperature < 35.0
    return Key(name="hypothermia", present=present, reason=f"Temp {v.temperature} < 35.0")


# --- Multi-vital named-syndrome detectors, FIXED absolute thresholds ---
# (extracted from the second of the two source methods)

def septic_shock(v: VitalsObservation) -> Key:
    present = (
        v.oxygen_saturation < 92.0
        and v.heart_rate > 140
        and v.respiratory_rate > 35
        and v.temperature > 38.5
    )
    return Key(
        name="septic_shock",
        present=present,
        reason=("O2<92 and HR>140 and RR>35 and temp>38.5" if present
                 else "not all septic_shock conditions met"),
    )


def respiratory_distress(v: VitalsObservation) -> Key:
    present = v.oxygen_saturation < 90.0 and v.respiratory_rate > 45
    return Key(
        name="respiratory_distress",
        present=present,
        reason="O2<90 and RR>45" if present else "not all respiratory_distress conditions met",
    )


def hypovolemic_shock(v: VitalsObservation) -> Key:
    present = v.heart_rate > 150 and v.oxygen_saturation < 88.0
    return Key(
        name="hypovolemic_shock",
        present=present,
        reason="HR>150 and O2<88" if present else "not all hypovolemic_shock conditions met",
    )


ALL_DETECTORS = (
    critical_o2,
    warning_o2,
    tachycardia,
    bradycardia,
    tachypnea,
    fever,
    hypothermia,
    septic_shock,
    respiratory_distress,
    hypovolemic_shock,
)


def detect_all(v: VitalsObservation):
    """Run every registered detector and return the resulting Keys.

    Guards against a copy-paste detector bug silently dropping a Key:
    registry.observe() feeds this straight into zeta.KeySet, which
    de-dupes by name with no warning, so two detectors sharing a name
    by accident would silently lose one of them with no error anywhere.
    """
    keys = [detector(v) for detector in ALL_DETECTORS]
    names = [k.name for k in keys]
    if len(names) != len(set(names)):
        dupes = sorted({n for n in names if names.count(n) > 1})
        raise AssertionError(f"detect_all() produced duplicate Key names: {dupes}")
    return keys
