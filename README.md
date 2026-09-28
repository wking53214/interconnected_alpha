# interconnected_alpha

**Role in the governed action stack:** OBSERVATION — raw signals → named **Keys** for the Locks layer.

```text
α Alpha (Keys) → ζ Zeta (Locks) → β Beta (Decision) → δ Delta (custody)
```

Part of the composable decision spine. Live orchestrated path: [observe-perceive](https://github.com/wking53214/observe-perceive). Locks: [interconnected_zeta](https://github.com/wking53214/interconnected_zeta).

---

Detects named **Keys** in raw pediatric vitals — the first stage of the
4-repo pipeline, feeding directly into `interconnected_zeta`'s Locks.

## Why this exists

Like `zeta`, this is an **extraction**, not a fresh invention. Two
methods in OBSERVE's `RiskAdapters` (`observe_consolidated.py`) already
compute named clinical signals — but each one only as an inline `if`
branch inside a single accumulated risk score, never as a standalone,
independently testable unit:

| Detector group | Extracted from | Threshold style |
|---|---|---|
| `critical_o2`, `warning_o2`, `tachycardia`, `bradycardia`, `tachypnea`, `fever`, `hypothermia` | `RiskAdapters.heuristic` (`observe_consolidated.py:292-340`) | Age-adjusted, via `PEDIATRIC_NORMS` + `get_age_group` (`observe_consolidated.py:113-119, 247-257`, copied verbatim) |
| `septic_shock`, `respiratory_distress`, `hypovolemic_shock` | `RiskAdapters.behavioral_vaccine` (`observe_consolidated.py:517-534`) | **Fixed absolute thresholds — NOT age-adjusted.** This is a real asymmetry in the source, reproduced faithfully rather than smoothed over. |

**A subtlety preserved on purpose:** `warning_o2` is an `elif` under
`critical_o2` in the source. This isn't a vacuous ordering — every
age-adjusted `o2_low` threshold (90/90/91/92/91) is *above* 88, so
"O2 < 88" always also satisfies "O2 < o2_low". Without excluding the
critical case explicitly, `warning_o2` would fire every time
`critical_o2` does. `warning_o2()` reproduces the exclusion explicitly
(see `test_warning_o2_mutually_exclusive_with_critical_o2`).

## What's explicitly out of scope

`RiskAdapters.behavioral_vaccine` also computes a `BASE_RISK` score and
two `BENIGN_PATTERN` suppressions (`fever_response`, `crying_baby`) that
*reduce* an accumulated score based on context. Those don't fit the Key
model — they're score modulation, not condition detection — and aren't
extracted here.

**Also dropped, caught by adversarial review:** the per-syndrome
severity weights the source adds on top of each boolean match
(`score += 0.40` for `septic_shock`, `+= 0.35` for the other two,
`observe_consolidated.py:524,529,534`) — even though these sit *inside*
the line range claimed as extracted. An earlier draft of this README
didn't mention that; leaving it out silently would have overstated
fidelity.

**On `Key.confidence`:** every detector here always returns
`confidence=1.0`. That's intentional — each check is a deterministic
threshold or boolean-AND comparison, with no probabilistic uncertainty
in the detection itself. The source's severity weights are a different
concept (how much a pattern should count toward an aggregate score) than
detection confidence (how sure we are the pattern is present), and
neither that weighting nor the source's separate data-completeness/
alert-context confidence values are reproduced here — both belong to the
source's overall risk-fusion output, not to any single named condition.

## API

```python
from alpha import VitalsObservation, observe

vitals = VitalsObservation(
    heart_rate=145, oxygen_saturation=90.0,
    respiratory_rate=36, temperature=39.6, age_months=14,
)

keys = observe(vitals)  # -> zeta.KeySet, ready to hand to a LockEvaluator
print(keys.names_present())  # {'septic_shock', 'tachycardia', 'fever', ...}
```

Feeding straight into `zeta`:

```python
from datetime import datetime
from zeta import Combination, LockEvaluator, LockRegistry, LockSpec
from alpha import VitalsObservation, observe

registry = LockRegistry([
    LockSpec(lock_id="sepsis_lock",
             required_keys=("septic_shock", "respiratory_distress", "hypovolemic_shock"),
             combination=Combination.OR, force=True, lock_seconds=3600),
])
evaluator = LockEvaluator(registry)

keys = observe(VitalsObservation(heart_rate=145, oxygen_saturation=90.0,
                                  respiratory_rate=36, temperature=39.6, age_months=14))
result = evaluator.evaluate("patient_1", keys, "sepsis_lock", datetime.now())
```

See `examples/pediatric_discharge.py` for the full timeline.

## Where this fits

```
interconnected_alpha  -- (this repo) raw vitals -> named Keys
interconnected_zeta   -- Keys -> Locks -> open/closed decisions
interconnected_beta   -- Lock states -> governance rules -> a decision + narrative
interconnected_delta  -- records the decision, tracks execution, verifies outcome
```

## Tests

```
pip install -e ".[dev]"
pytest
```

62 tests. Depends only on `zeta` (path/git dependency) — no other
external packages.
