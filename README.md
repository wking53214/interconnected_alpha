# interconnected_alpha (α)

Extracted **observation → named Keys** layer. Version `0.2.0`. Domain packs (`alpha.packs`) turn raw observations into named Keys; two packs ship: pediatric vitals (`alpha.packs.pediatric_vitals`) and service health (`alpha.packs.service_health`, synthetic, a proof that the contract is not tied to medicine), and `alpha.core` is the domain-blind contract both implement. Depends on [`interconnected_zeta`](https://github.com/wking53214/interconnected_zeta) (`zeta.Key` / `zeta.KeySet`).

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

`observe(vitals) -> KeySet` is the pack's public façade (`alpha/packs/pediatric_vitals/registry.py`). `ALL_DETECTORS` is the ordered list. Unknown future detectors are not dynamically loaded.

### Layout

```
alpha/core/pack.py     DomainPack, Parameter, PackRegistry (domain-blind)
alpha/cns_connector.py binding a KeySet for CNS (domain-blind)
alpha/packs/pediatric_vitals/
    vitals.py          VitalsObservation
    thresholds.py      PEDIATRIC_NORMS, get_age_group
    detectors.py       ten named detectors
    registry.py        observe()
    pack.py            PediatricVitalsPack (the DomainPack declaration)
alpha/packs/service_health/
    observation.py     ServiceObservation (p95 latency, error rate, queue depth, tier)
    thresholds.py      the declared parameters, and SERVICE_NORMS derived from them
    detectors.py       five named detectors
    registry.py        observe()
    pack.py            ServiceHealthPack
examples/pediatric_discharge.py
examples/service_degradation.py   the same wiring in another industry
```

## Domain packs (`alpha.core`)

`alpha.core` holds a domain-blind contract and a registry; it names no domain, and neither does anything else in `alpha` outside `alpha/packs/` (a test checks that).
The pediatric-vitals detectors moved into the pack `alpha.packs.pediatric_vitals` with no change to what they say: a digest of every detector output
(names, presence, confidence, reasons, key fingerprint) over a grid of 20,160 readings, captured from the code before the move
(`tests/golden_pediatric_keys.json`), is reproduced exactly. The old top-level names (`alpha.VitalsObservation`, `alpha.observe`, `alpha.PEDIATRIC_NORMS`,
`alpha.detect_all` and the rest) and module paths (`alpha.vitals`, `alpha.detectors`, ...) are gone: a deliberate clean break, since alpha has no tags.

A pack (`alpha.core.DomainPack`) declares its `NAME`, `VERSION` (MAJOR.MINOR.PATCH), `DOMAIN` and the Key names it can emit (`KEYS`),
and its `parameters()` as data: each `Parameter` is named, typed (an exact `int` or `float`, finite, never a `bool`), bounded
(`minimum <= value <= maximum`), described, and carries who approved it, the approval date and the justification. There are no defaults.
`PackRegistry.register` validates totally, listing every violation in one `PackValidationError`, and refuses an invalid pack, a pack whose
name is already registered, and anything that is not a `DomainPack`. `PackRegistry.observe` holds a pack to what it declared: the result
must be exactly a `zeta.KeySet` (a subclass is refused) and every Key must be one the pack declared. The parameters are read once, at
registration, and that snapshot is what the registry keeps. `pack_identity(pack)` is `pack:<name>/<version>`, for a producer to record with
what it observed (for example in the origin's `transformation` field).

**The second pack.** `alpha.packs.service_health` takes a `ServiceObservation` (p95 latency in ms, error rate as a fraction, queue depth, and a tier of `interactive` or `batch`) and emits five Keys: `latency_high`, `latency_critical`, `error_burst`, `queue_backlog` and `degraded_service` (high latency together with an error burst). Its 8 thresholds are declared as bounded parameters and are the single source the detectors read. They are synthetic, tuned to no real service, and declared "unapproved" the same way. A suite (`tests/test_two_packs_one_contract.py`) holds both packs to the same contract: both register in one registry, are held to the Keys they declared, observe deterministically, record their identity in the existing `origin.transformation` field (which changes the bound content, so the identity is part of what is bound), and feed Zeta locks. `examples/service_degradation.py` runs a service timeline through a Zeta lock.

The pediatric pack declares its 25 age-group thresholds (`PEDIATRIC_NORMS`) as bounded parameters. **Nobody has approved them**: `approved_by` says
"unapproved: copied verbatim from OBSERVE ...", `approval_date` is the date of the declaration, and the justification repeats that they are not
independently clinically validated. The fixed absolute thresholds of `critical_o2`, `hypothermia` and the three syndrome detectors are still literals in
`detectors.py`, not yet declared parameters. Naming a real reviewer is the pack owner's decision.

Limits, stated plainly: a pack's identity is a producer's claim and nothing here authenticates it; "approved by" is recorded and not
checked; the contract validates the shape of a declaration, not whether a threshold is right for its domain. Modelled on the cassette
contract in sentinel_os (kernel contract, declared bounded parameters, fail-loud load); no sentinel_os code is used.

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
| Dependency | `zeta` is pinned by commit in `pyproject.toml` (`tests/test_zeta_pin.py` holds the pin), so moving it is a reviewed change. It is a git dependency, not on a package index. |
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
from alpha.packs.pediatric_vitals import VitalsObservation, observe

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

## Optional CNS connection

alpha does not need CNS. It has no runtime dependency on it (its only dependency is still zeta), nothing in the package imports CNS when it loads, and `observe` never imports it (`tests/test_cns_independence.py` checks this with CNS blocked). `alpha/cns_connector.py` is the one place that knows CNS exists. Install it with `pip install 'alpha[cns] @ git+https://github.com/wking53214/interconnected_alpha'` (CNS needs Python 3.10+); without CNS, computing a digest raises `CnsNotInstalled` and nothing else changes.

It makes the `zeta.KeySet` that `observe` returns **bindable** to a verdict in CNS's shared gate contract (`cns.gate`), so a verdict about detected keys can be checked against those keys:

| Output | Bound content | Subject |
|---|---|---|
| `observe(...)` -> `KeySet` | `min_confidence`, and for every key (listed by name, so insertion order cannot matter): `name`, `present`, `confidence`, `reason` | `alpha.keyset` |

`keyset_digest(keys)` and `binds(verdict, keys)` are the whole surface; `keyset_content(keys)` returns the plain content (no CNS needed). `binds` is true only for a verdict issued against exactly those keys, and false for an unbound or hand-built one. The `reason` text is bound because it carries the readings and thresholds each detector compared, so the same keys firing on a different reading is a different record. alpha identifies no patient (see non-goals), so by default identical keys for two patients bind alike.

**Binding keys to a run.** Pass `context=` to `keyset_content`, `keyset_digest` or `binds`: a mapping with exactly `schema` (`"spine-context/1"`), `entity_id`, `event_id` and `run_id`, all non-empty strings. The content then gains `context` and `present_names`, the sorted names zeta's own `KeySet` rule treats as present (present, and at or above `min_confidence`), so a reader does not re-derive that rule. A malformed context or unknown schema raises. Without a context the content, and every existing digest, is unchanged. alpha still identifies nobody on its own: the caller supplies the context, and CNS's strict trace is what refuses a run whose stages disagree. The content also carries `keyset_fingerprint`, zeta's own SHA-256 of exactly what the KeySet holds (every Key's name, presence, confidence and reason, and `min_confidence`). A zeta `LockResult` records the same value for the KeySet it was evaluated from, which is how CNS checks that a result was evaluated from the KeySet alpha produced, instead of trusting a digest the binder names. Two sets of readings that list the same present Keys have different fingerprints. A KeySet from a zeta that cannot fingerprint is refused under a context. It is a fact about the object, not a signature: alpha still cannot show that the readings themselves are authentic.

**Recording an origin claim.** Pass `origin=` to `keyset_content`, `keyset_digest` or `binds`: a mapping with exactly `source`, `producer`, `observed_at` (ISO 8601 text, checked with `datetime.fromisoformat`), `collection_context` and `transformation`, all non-empty `str` (no subclasses). A wrong type raises `TypeError`, and a missing, extra or empty key or an unparseable `observed_at` raises `ValueError`, each naming the field. The mapping is copied once and the copy is validated and bound. The content then gains `origin`; without it the content, and every existing digest, is unchanged (tested). So when asked, alpha records who claims to have produced the readings (`producer`), from what source (`source`), when they were observed (`observed_at`), in what collection context (`collection_context`) and by what transformation (`transformation`). Changing any one of the five changes the digest, so a verdict bound to the content is bound to that claim. The `keyset_fingerprint` is unchanged by an origin: it still covers exactly what the KeySet holds and nothing about where the readings came from.

These are the producer's own assertions, bound into the digest lineage. They are not proof, and each of these is a separate thing alpha does not establish: source authenticity (that the readings came from the named source), producer identity (that the named producer is who it says), authorization (that the producer was allowed to supply them) and truthfulness (that the readings or the claim are correct). alpha performs no authentication and makes no authorization or truthfulness claim; the only check on `observed_at` is that it parses.

This is **binding only**, on purpose. alpha detects named keys; it does not evaluate locks, policy or authorization, so it offers no gate, no PASS / RETRY / BREACH mapping and no chain. Whoever judges the keys owns the verdict; alpha only lets that verdict be tied to the keys it was about.

Apache-2.0.
