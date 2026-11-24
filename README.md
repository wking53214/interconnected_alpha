# interconnected_alpha (α)

Extracted **observation → named Keys** layer. Version `0.2.0`. Domain packs (`alpha.packs`) turn raw observations into named Keys; two packs ship: pediatric vitals (`alpha.packs.pediatric_vitals`) and service health (`alpha.packs.service_health`, synthetic, a proof that the contract is not tied to medicine), and `alpha.core` is the domain-blind contract both implement. Depends on [`interconnected_zeta`](https://github.com/wking53214/interconnected_zeta) (`zeta.Key` / `zeta.KeySet`).

## Role Within ≡TACK

- **What it is.** The observation stage of the small reference spine: it turns a raw observation into named Keys using a domain pack.
- **Authority matrix.** Evaluation only (detects named conditions). It does not define policy, enforce, authorize, authenticate or store evidence.
- **Owns.** The pack contract (`alpha.core`), two packs, and the CNS binding of a `KeySet`.
- **Does not own.** Locks (zeta), decisions (beta), custody (delta), the orchestrator path (observe-perceive), or whether thresholds are clinically right (nobody approved the pediatric norms; see section 2).
- **Depends on.** `zeta`, pinned by commit in `pyproject.toml`. CNS is optional.
- **Depended on by.** `zeta`, `beta` and `delta` are described as the later stages. Whether each imports alpha: UNKNOWN (not inspected here). observe-perceive does not use it (stated in section 4, not re-checked).
- **Fail behavior.** Closed on malformed input: `None`, non-finite, `bool` and subclass values are refused at construction, so a missing or non-numeric reading cannot become "not present". Open on out-of-range numbers: there is no range check, so an impossible but finite value is judged like any other number. EXECUTED 2026-11-17: an oxygen saturation of 185 (a slip for 85) was accepted and returned no Key present, and a heart rate of -40 returned `bradycardia`. A pack is trusted in-process code, and its identity and "approved by" text are claims nothing authenticates.

## 1. Pipeline Position & Role

**OBSERVATION.** First stage of the extracted decision spine.

```text
α Alpha (this repo) → ζ Zeta (Locks) → β Beta (Decision) → δ Delta (custody)
```

The order above is the design order. CNS's script `chains/spine_run.py` runs all four repos in this order (EXECUTED 2026-11-17: exit 0 against the four mains). observe-perceive's orchestrator does not call them.

The orchestrator path remains [`observe-perceive`](https://github.com/wking53214/observe-perceive). This repo extracts the named-condition detectors that were previously inline `if` branches inside OBSERVE's `RiskAdapters` score accumulator.

## 2. Full System Scope & Architectural Depth

α does one thing: given a `VitalsObservation`, run a closed set of detectors and return a `zeta.KeySet`.

### Input

`VitalsObservation` (frozen): `heart_rate`, `oxygen_saturation`, `respiratory_rate`, `temperature` (all required, finite floats); `age_months: Optional[int]`. Construction rejects `None` and non-finite values so a NaN cannot silently become `present=False` (indistinguishable from healthy).

This is **not** OBSERVE's full `VitalsSnapshot` (no `patient_id`, no timestamp, no open context dict). Only fields the extracted detectors actually read.

### Detector groups (fidelity, not harmony)

| Group | Source | Threshold style | Names |
|---|---|---|---|
| Single-vital | `RiskAdapters.heuristic` (`observe_consolidated.py:292-340`) | **Age-adjusted** via `PEDIATRIC_NORMS` + `get_age_group` | `critical_o2`, `warning_o2`, `tachycardia`, `bradycardia`, `tachypnea`, `fever`, `hypothermia` |
| Named syndrome | `RiskAdapters.behavioral_vaccine` (`observe_consolidated.py:517-534`) | **Fixed absolute thresholds, not age-adjusted** | `septic_shock`, `respiratory_distress`, `hypovolemic_shock` |

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
(names, presence, confidence, reasons and each set's `min_confidence`; zeta's key fingerprint is a function of exactly those fields) over a grid of 75,264 readings, captured from the code before the move
(`tests/golden_pediatric_keys.json`), was reproduced exactly (at commit a54d1dc; the file was re-captured on 2026-11-23 when the heart rate, respiratory rate and newborn fever limits were re-derived, and now pins the new limits). The old top-level names (`alpha.VitalsObservation`, `alpha.observe`, `alpha.PEDIATRIC_NORMS`,
`alpha.detect_all` and the rest) and module paths (`alpha.vitals`, `alpha.detectors`, ...) are gone: a deliberate clean break, since alpha has no tags.

A pack (`alpha.core.DomainPack`) declares its `NAME`, `VERSION` (MAJOR.MINOR.PATCH), `DOMAIN` and the Key names it can emit (`KEYS`),
and its `parameters()` as data: each `Parameter` is named, typed (an exact `int` or `float`, finite, never a `bool`), bounded
(`minimum <= value <= maximum`), described, and carries who approved it, the approval date and the justification. There are no defaults.
`PackRegistry.register` lists every violation it finds in one `PackValidationError` (a pack's relations between parameters are checked only once every parameter is individually valid, so a pack with a bad bound reports the bound first), and refuses an invalid pack, a pack whose
name is already registered, and anything that is not a `DomainPack`. `PackRegistry.observe` holds a pack to what it declared: the result
must be exactly a `zeta.KeySet` (a subclass is refused), every Key must be one the pack declared and every declared Key must be there, `present` must be an exact `bool`, `confidence` an exact `int` or `float` (never a `bool`), `reason` a `str`, and the set's `min_confidence` must stay 0.0 (a floor is the consumer's choice; a pack that raised its own would hide its Keys from every lock). The parameters are read once, at
registration, and that snapshot is what the registry keeps, together with its own copies of the parameters and the `NAME`, `VERSION` and
`KEYS` it read and validated once. `PackRegistry.observe` returns a `KeySet` the registry built itself, from exact `Key` objects with exact `str` names read
through the classes' own accessors, so nothing a pack attaches to its objects reaches the caller. `PackRegistry.identity(name)` is
`pack:<name>/<version>` from the values read at registration, for a producer to record with what it observed (for example in the origin's
`transformation` field); `pack_identity(pack)` reads the pack as it is now.

**What the contract does and does not do.** A pack is trusted, in-process code: the registry guards what it validated (the identity, the Key names and its own copies of the parameters) against a pack that changes
after registration, not against a pack that is wrong in a consistent way. At registration the registry now hands the copies it validated back to the pack through `adopt_parameters` (a method a pack may override; the default does nothing), and both shipped packs build their threshold table from those copies, so the values checked are the values used. EXECUTED 2026-11-19: a pack whose `parameters()` gave valid values at registration and different values afterwards observed with the registered values, in both shipped packs (`tests/test_thresholds_come_from_the_registry.py`). A pack used without a registry still reads its own `parameters()`, and a third-party pack that does not override `adopt_parameters` is not covered. The module-level `observe` functions (the one the example in section 6 calls) use the default tables and pass through no registry at all. A pack states relations its bounds cannot (for example a critical limit not
below a high one) by overriding `parameter_problems`; the registry calls it on the validated copies and refuses the pack with the messages it returns,
and both shipped packs state theirs. Every declared Key must be returned on every observation, present or not. It does not check that approval text is
true, that a pack's relations are the right ones; it cannot stop a caller from rebinding a module's names. Both observation types (`VitalsObservation`, `ServiceObservation`) now refuse a `bool`,
a subclass, a non-finite number or an integer too large for a float; `age_months` is `None` or a non-negative exact `int`.

**The second pack.** `alpha.packs.service_health` takes a `ServiceObservation` (p95 latency in ms, error rate as a fraction, queue depth, and a tier of `interactive` or `batch`) and emits five Keys: `latency_high`, `latency_critical`, `error_burst`, `queue_backlog` and `degraded_service` (high latency together with an error burst). Its 8 thresholds are declared as bounded parameters and are what the detectors use: each pack builds its threshold table from its own declared parameters, and the tables are read-only. They are synthetic, tuned to no real service, and declared "unapproved" the same way. A suite (`tests/test_two_packs_one_contract.py`) holds both packs to the same contract: both register in one registry, are held to the Keys they declared, observe deterministically, record their identity in the existing `origin.transformation` field (which changes the bound content, so the identity is part of what is bound), and feed Zeta locks. `examples/service_degradation.py` runs a service timeline through a Zeta lock.

The pediatric pack declares its 35 age-group thresholds (`PEDIATRIC_NORMS`) as bounded parameters. **Nobody has approved them**: `approved_by` says
"unapproved: provisional proxies re-derived 2026-11-23 ...", `approval_date` is the date of the declaration, and the justification repeats that they are not
independently clinically validated. The fixed absolute thresholds of `critical_o2`, `hypothermia` and the three syndrome detectors are still literals in
`detectors.py`, not yet declared parameters. Naming a real reviewer is the pack owner's decision.

Limits, stated plainly: a pack's identity is a producer's claim and nothing here authenticates it; "approved by" is recorded and not
checked; the contract validates the shape of a declaration, not whether a threshold is right for its domain. Modelled on the cassette
contract in sentinel_os (kernel contract, declared bounded parameters, fail-loud load); no sentinel_os code is used.

## 3. What It Does NOT Do / Non-Goals

- Does **not** fuse scores, select engines, or emit a regime. That is OBSERVE.
- Does **not** extract `BASE_RISK` or `BENIGN_PATTERN` suppressions (`fever_response`, `crying_baby`), those modulate an accumulated score, they are not Keys.
- Does **not** reproduce per-syndrome severity weights or data-completeness / alert-context confidence.
- Does **not** evaluate Locks, policy, or authorization.
- Does **not** persist, ledger, or identify a patient.
- Does **not** load detectors dynamically. Two packs ship (pediatric vitals and a synthetic service-health pack); the pack contract in `alpha.core` lets a caller register another in code, but no plugin discovery exists.
- Does **not** call PERCEIVE, Conservation Kernel, or sentinel_os.
- Does **not** sign anything, hold a key, or check a signature. Signed lock results are zeta's and beta's (see "How alpha's output feeds signed lock results").

## 4. Brutally Honest Current Status & Gaps

| Gap | Detail |
|---|---|
| Domain | One clinical pack (pediatric vitals) and one synthetic pack (service health). Not a general observation runtime. Driving/ascent/IVR detectors were **not** extracted. |
| Confidence | Always `1.0`. Callers who need probabilistic detection must do it elsewhere. |
| Age-group holes | `get_age_group(None)` and ages outside the table follow source behavior; do not assume clinical completeness. |
| Uncalibrated norms | `PEDIATRIC_NORMS`: heart rate, respiratory rate and newborn fever limits re-derived 2026-11-23 from Fleming 2011, Goldstein 2005 and AAP 2021 as provisional proxies (OBSERVE's low heart-rate limit rose with age); the rest copied from OBSERVE. The old "child" group (3 to 18 years) was split on 2026-11-23 into preschool, school and adolescent (provisional). Not independently clinically validated. Commercial red team: OBSERVE pediatric path is **not commercially relevant as-is** (missed detections filed as test skips). |
| Dependency | `zeta` is pinned by commit in `pyproject.toml` (`tests/test_zeta_pin.py` holds the pin), so moving it is a reviewed change. It is a git dependency, not on a package index. |
| Orchestrator-path wiring | observe-perceive still runs `observe_consolidated.py` RiskAdapters inline. α is **not imported** by the orchestrator. Dual implementation: extract vs source of extraction. |
| Threading / IO | Pure functions. No store. |
| Readings are not authenticated, even when downstream is signed | A signature on a zeta lock result proves who held the signer, not that the readings alpha was given were real. alpha cannot show the readings are authentic (see "How alpha's output feeds signed lock results"). |

`pip install -e ".[dev]" && pytest`. Library, not a service. EXECUTED 2026-11-19, Python 3.13, in a fresh environment that held only this repo and its pins: that command gives 281 passed, 3 skipped (the three need CNS). With the `cns` extra installed, 385 passed and none skipped (run without `ALPHA_REQUIRE_CNS=1`; CI's second job sets it). Both examples ran to the end. Not run: GitHub CI, Python 3.10 to 3.12. The earlier "62 tests" figure here was out of date.

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
                       → ζ.LockEvaluator.evaluate(_all)   (lock results signed if a signer is plugged in)
                            → β.DecisionEngine.decide   (refuses unsigned or badly signed lock results if a checker is plugged in)
                                 → δ.DecisionLedger.append   (signed checkpoints can be published to an outside anchor)
```

Who runs this order: CNS's script `chains/spine_run.py`, not observe-perceive's orchestrator (see section 1 for the evidence).

Example: `examples/pediatric_discharge.py` (full α→ζ timeline).  
Source of extraction: [`OBSERVE`](https://github.com/wking53214/OBSERVE) / `observe_consolidated.py` in observe-perceive.  
Hub: observe-perceive **does not yet substitute α for RiskAdapters**.

## How alpha's output feeds signed lock results

alpha is the first link in a chain that can now be signed and checked end to end. alpha itself signs and checks nothing.

1. **alpha** turns a raw observation into a `zeta.KeySet` (`observe`). Each `Key` carries its name, presence, confidence and a `reason` that records the readings and thresholds compared.
2. **zeta** evaluates its locks from that `KeySet`. `KeySet.fingerprint()` is a SHA-256 of exactly what the set holds (`min_confidence` and every Key's name, presence, confidence and reason). Every `LockResult` records it as `keyset_fingerprint`, together with the `entity_id`. If the operator plugs in a signer (`LockEvaluator(registry, signer=...)`), zeta signs every result over those fields, so the signature covers which KeySet the lock state was judged from.
3. **beta**, when the operator plugs in a checker (`DecisionEngine(..., lock_result_signer=..., lock_result_verifier=...)`), refuses any lock result whose signature is missing or does not check out, and makes no Decision.
4. **delta** records the Decision in its hash-chained ledger and can publish signed checkpoints to an outside anchor.

What this means for alpha's output:

- **A different reading is a different signature.** Because the `reason` text is part of the `KeySet` fingerprint, the same Keys firing on a different reading gives a different `keyset_fingerprint`, so a signed lock result cannot be reused for other readings.
- **alpha's output is the one input nobody signs.** The signature starts at zeta. A signed lock result proves the holder of the signer evaluated that exact `KeySet`. It does not prove the readings given to `observe` were real, that the sensor or the person entering them was honest, or that the pack's thresholds are clinically right. alpha cannot show any of these.
- **A KeySet that cannot fingerprint is refused under a context** (see the CNS section).
- **Nothing here is protected unless the operator plugs both in.** With no signer in zeta and no checker in beta, results are unsigned and anyone can build one. Even with both, the signer runs in the same process as the evaluator, so code there that can call it can sign a lock result no evaluation produced. A separate signer process is the next step.

This repo's own tests and API are unchanged by this: its only dependency is still zeta, at the older pin noted in section 4.

## Optional CNS connection

alpha does not need CNS. It has no runtime dependency on it (its only dependency is still zeta), nothing in the package imports CNS when it loads, and `observe` never imports it (`tests/test_cns_independence.py` checks this with CNS blocked). `alpha/cns_connector.py` is the one place that knows CNS exists. Install it with `pip install 'alpha[cns] @ git+https://github.com/wking53214/interconnected_alpha'` (CNS needs Python 3.10+); without CNS, computing a digest raises `CnsNotInstalled` and nothing else changes.

It makes the `zeta.KeySet` that `observe` returns **bindable** to a verdict in CNS's shared gate contract (`cns.gate`), so a verdict about detected keys can be checked against those keys:

| Output | Bound content | Subject |
|---|---|---|
| `observe(...)` -> `KeySet` | `min_confidence`, and for every key (listed by name, so insertion order cannot matter): `name`, `present`, `confidence`, `reason` | `alpha.keyset` |

`keyset_digest(keys)` and `binds(verdict, keys)` are the whole surface; `keyset_content(keys)` returns the plain content (no CNS needed). `binds` is true only for a verdict that names exactly those keys (the subject and their digest), and false for an unbound one or one that names other keys. It compares what a verdict names and does not check who made it: a `GateResult` typed by hand with the right subject and digest binds too (EXECUTED 2026-11-17), so `binds` alone is not evidence that any gate judged the keys. The `reason` text is bound because it carries the readings and thresholds each detector compared, so the same keys firing on a different reading is a different record. alpha identifies no patient (see non-goals), so by default identical keys for two patients bind alike.

**Binding keys to a run.** Pass `context=` to `keyset_content`, `keyset_digest` or `binds`: a mapping with exactly `schema` (`"spine-context/1"`), `entity_id`, `event_id` and `run_id`, all non-empty strings. The content then gains `context` and `present_names`, the sorted names zeta's own `KeySet` rule treats as present (present, and at or above `min_confidence`), so a reader does not re-derive that rule. A malformed context or unknown schema raises. Without a context the content, and every existing digest, is unchanged. alpha still identifies nobody on its own: the caller supplies the context, and CNS's strict trace is what refuses a run whose stages disagree. The content also carries `keyset_fingerprint`, zeta's own SHA-256 of exactly what the KeySet holds (every Key's name, presence, confidence and reason, and `min_confidence`). A zeta `LockResult` records the same value for the KeySet it was evaluated from, which is how CNS checks that a result was evaluated from the KeySet alpha produced, instead of trusting a digest the binder names. Two sets of readings that list the same present Keys have different fingerprints. A KeySet from a zeta that cannot fingerprint is refused under a context. It is a fact about the object, not a signature: alpha still cannot show that the readings themselves are authentic.

**Recording an origin claim.** Pass `origin=` to `keyset_content`, `keyset_digest` or `binds`: a mapping with exactly `source`, `producer`, `observed_at` (ISO 8601 text, checked with `datetime.fromisoformat`), `collection_context` and `transformation`, all non-empty `str` (no subclasses). A wrong type raises `TypeError`, and a missing, extra or empty key or an unparseable `observed_at` raises `ValueError`, each naming the field. The mapping is copied once and the copy is validated and bound. The content then gains `origin`; without it the content, and every existing digest, is unchanged (tested). So when asked, alpha records who claims to have produced the readings (`producer`), from what source (`source`), when they were observed (`observed_at`), in what collection context (`collection_context`) and by what transformation (`transformation`). Changing any one of the five changes the digest, so a verdict bound to the content is bound to that claim. The `keyset_fingerprint` is unchanged by an origin: it still covers exactly what the KeySet holds and nothing about where the readings came from.

These are the producer's own assertions, bound into the digest lineage. They are not proof, and each of these is a separate thing alpha does not establish: source authenticity (that the readings came from the named source), producer identity (that the named producer is who it says), authorization (that the producer was allowed to supply them) and truthfulness (that the readings or the claim are correct). alpha performs no authentication and makes no authorization or truthfulness claim; the only check on `observed_at` is that it parses.

This is **binding only**, on purpose. alpha detects named keys; it does not evaluate locks, policy or authorization, so it offers no gate, no PASS / RETRY / BREACH mapping and no chain. Whoever judges the keys owns the verdict; alpha only lets that verdict be tied to the keys it was about.

Apache-2.0.
