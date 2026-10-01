# interconnected_alpha (α)

Extracted **observation → named Keys** layer. Version `0.1.0`. Pediatric vitals only. Depends on [`interconnected_zeta`](https://github.com/wking53214/interconnected_zeta) (`zeta.Key` / `zeta.KeySet`).

## 1. Pipeline Position & Role

**OBSERVATION.** First stage of the extracted decision spine.

```text
α Alpha (this repo) → ζ Zeta (Locks) → β Beta (Decision) → δ Delta (custody)
```

Live orchestrated path remains [`observe-perceive`](https://github.com/wking53214/observe-perceive). This repo extracts the named-condition detectors that were previously inline `if` branches inside OBSERVE's `RiskAdapters` score accumulator.

## 2. Full System Scope & Architectural Depth

α does one thing: given a `VitalsObservation`, run a closed set of detectors and return a `zeta.KeySet`.

### Input

`VitalsObservation` (frozen): `heart_rate`, `oxygen_saturation`, `respiratory_rate`, `temperature` (all required, finite floats); `age_months: Optional[int]`. Construction rejects `None` and non-finite values so a NaN cannot silently become `present=False` (indistinguishable from healthy).

This is **not** OBSERVE's full `VitalsSnapshot` (no `patient_id`, no timestamp, no open context dict). Only fields the extracted detectors actually read.

### Detector groups (fidelity, not harmony)

| Group | Source | Threshold style | Names |
|---|---|---|---|
| Single-vital | `RiskAdapters.heuristic` (`observe_consolidated.py:292-340`) | **Age-adjusted** via `PEDIATRIC_NORMS` + `get_age_group` | `critical_o2`, `warning_o2`, `tachycardia`, `bradycardia`, `tachypnea`, `fever`, `hypothermia` |
| Named syndrome | `RiskAdapters.behavioral_vaccine` (`observe_consolidated.py:517-534`) | **Fixed absolute thresholds — not age-adjusted** | `septic_shock`, `respiratory_distress`, `hypovolemic_shock` |

The age-adjustment asymmetry is reproduced on purpose. Harmonizing it would overstate fidelity.

`warning_o2` is an `elif` under `critical_o2` in the source: every age-adjusted `o2_low` is above 88, so without exclusion `warning_o2` would fire whenever `critical_o2` does. The exclusion is tested (`test_warning_o2_mutually_exclusive_with_critical_o2`).

Every detector returns `Key.confidence = 1.0`. Deterministic threshold matches have no detection uncertainty. Source severity weights (`score += 0.40` / `0.35`) are **not** stuffed into `confidence`.

`observe(vitals) -> KeySet` is the public façade (`alpha/registry.py`). `ALL_DETECTORS` is the ordered list. Unknown future detectors are not dynamically loaded.

### Layout

```
alpha/vitals.py        VitalsObservation
alpha/thresholds.py    PEDIATRIC_NORMS, get_age_group
alpha/detectors.py     ten named detectors
alpha/registry.py      observe()
examples/pediatric_discharge.py
```

## 3. What It Does NOT Do / Non-Goals

- Does **not** fuse scores, select engines, or emit a regime. That is OBSERVE.
- Does **not** extract `BASE_RISK` or `BENIGN_PATTERN` suppressions (`fever_response`, `crying_baby`) — those modulate an accumulated score, they are not Keys.
- Does **not** reproduce per-syndrome severity weights or data-completeness / alert-context confidence.
- Does **not** evaluate Locks, policy, or authorization.
- Does **not** persist, ledger, or identify a patient.
- Does **not** generalize beyond pediatric vitals. There is no plugin detector API.
- Does **not** call PERCEIVE, Conservation Kernel, or sentinel_os.

## 4. Brutally Honest Current Status & Gaps

| Gap | Detail |
|---|---|
| Domain | Pediatric vitals demo. Not a general observation runtime. Driving/ascent/IVR detectors were **not** extracted. |
| Confidence | Always `1.0`. Callers who need probabilistic detection must do it elsewhere. |
| Age-group holes | `get_age_group(None)` and ages outside the table follow source behavior; do not assume clinical completeness. |
| Uncalibrated norms | `PEDIATRIC_NORMS` copied from OBSERVE. Not independently clinically validated. Commercial red team: OBSERVE pediatric path is **not commercially relevant as-is** (missed detections filed as test skips). |
| Dependency | Git URL `zeta @ git+https://github.com/wking53214/interconnected_zeta` — **unpinned**. Default-branch drift can break α. |
| Live-path wiring | observe-perceive still runs `observe_consolidated.py` RiskAdapters inline. α is **not imported** by the orchestrator. Dual implementation: extract vs source of extraction. |
| Threading / IO | Pure functions. No store. |

62 tests. `pip install -e ".[dev]" && pytest`. Library, not a service.

## 5. Core Invariants & Guarantees

- Fail-closed on illegal vitals (`None` / non-finite).
- Named Keys only; no silent score blob.
- `warning_o2` mutually exclusive with `critical_o2`.
- Syndrome thresholds remain unaadjusted (source asymmetry conserved).
- Detector output is a `zeta.Key` so ζ can combine it without re-deriving booleans.

No guarantee of clinical correctness, calibration, or completeness of observation.

## 6. Inputs, Outputs & Type Contracts

```python
from alpha import VitalsObservation, observe

vitals = VitalsObservation(
    heart_rate=145, oxygen_saturation=90.0,
    respiratory_rate=36, temperature=39.6, age_months=14,
)
keys = observe(vitals)          # zeta.KeySet
keys.names_present()            # set[str]
keys.is_present("septic_shock") # bool
keys.get("fever")               # zeta.Key | None
# Key: name, present, confidence=1.0, reason
```

## 7. Stack Integration Topology

```text
raw vitals
    → α.observe → zeta.KeySet
                       → ζ.LockEvaluator.evaluate(_all)
                            → β.DecisionEngine.decide
                                 → δ.DecisionLedger.append
```

Example: `examples/pediatric_discharge.py` (full α→ζ timeline).  
Source of extraction: [`OBSERVE`](https://github.com/wking53214/OBSERVE) / `observe_consolidated.py` in observe-perceive.  
Hub: observe-perceive **does not yet substitute α for RiskAdapters**.

Proprietary. Copyright (c) 2026 William King. All rights reserved. See LICENSE.
