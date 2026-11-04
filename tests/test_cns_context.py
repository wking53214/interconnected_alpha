"""alpha binds a KeySet to one pipeline run, and states which Keys count as present.

A KeySet digest covered the Keys and nothing about the observation behind them, so keys detected for two patients
bound alike. With a context the content names the entity, the event and the run, and lists ``present_names``: the
Keys zeta's own KeySet rule treats as present (present, and at or above min_confidence). CNS reads that list
instead of re-implementing zeta's rule.

These skip where ``cns`` is not installed. CI installs the extra and sets ALPHA_REQUIRE_CNS=1, so there they cannot skip.
"""
import os

import pytest

if os.environ.get("ALPHA_REQUIRE_CNS") == "1":  # CI: a missing cns is a failure, not a skip
    import cns.gate as gate
else:
    gate = pytest.importorskip("cns.gate")

from zeta import Key, KeySet  # noqa: E402

from alpha import VitalsObservation, observe  # noqa: E402
from alpha.cns_connector import CONTEXT_SCHEMA, KEYSET_SUBJECT, binds, keyset_content, keyset_digest  # noqa: E402

CTX = {"schema": CONTEXT_SCHEMA, "entity_id": "p1", "event_id": "ev-1", "run_id": "run-1"}
SICK = VitalsObservation(heart_rate=148, oxygen_saturation=90.0, respiratory_rate=36, temperature=39.6, age_months=14)


def test_without_a_context_the_content_carries_neither_context_nor_present_names():
    content = keyset_content(observe(SICK))
    assert set(content) == {"min_confidence", "keys"}


def test_with_a_context_the_content_names_the_run_and_lists_the_present_keys():
    keys = observe(SICK)
    content = keyset_content(keys, context=dict(CTX))
    assert content["context"] == CTX
    assert content["present_names"] == sorted(keys.names_present()) and content["present_names"]
    assert {k["name"] for k in content["keys"]} >= set(content["present_names"])


def test_present_names_agrees_with_zeta_at_the_confidence_boundary():
    """present_names is zeta's rule, not a copy of it: at the boundary, above, below, and with present=False."""
    keys = KeySet([
        Key(name="at_boundary", present=True, confidence=0.5),
        Key(name="above", present=True, confidence=0.9),
        Key(name="below", present=True, confidence=0.49),
        Key(name="absent_but_sure", present=False, confidence=1.0),
        Key(name="zero", present=True, confidence=0.0),
    ], min_confidence=0.5)
    names = keyset_content(keys, context=dict(CTX))["present_names"]
    assert names == ["above", "at_boundary"]
    for key in keys.all_keys():
        assert (key.name in names) == keys.is_present(key.name)


def test_present_names_does_not_depend_on_the_order_the_keys_were_added():
    a = KeySet([Key(name="a", present=True), Key(name="b", present=True)])
    b = KeySet([Key(name="b", present=True), Key(name="a", present=True)])
    assert keyset_digest(a, context=dict(CTX)) == keyset_digest(b, context=dict(CTX))


@pytest.mark.parametrize("change", [
    {"entity_id": "p2"}, {"event_id": "ev-2"}, {"run_id": "run-2"},
])
def test_keys_detected_for_another_entity_event_or_run_no_longer_bind_alike(change):
    keys = observe(SICK)
    assert keyset_digest(keys, context=dict(CTX)) != keyset_digest(keys, context={**CTX, **change})
    assert keyset_digest(keys, context=dict(CTX)) != keyset_digest(keys)


@pytest.mark.parametrize("bad, exc, match", [
    ({k: v for k, v in CTX.items() if k != "entity_id"}, ValueError, "exactly"),
    ({**CTX, "extra": "x"}, ValueError, "exactly"),
    ({**CTX, "run_id": ""}, ValueError, "non-empty"),
    ({**CTX, "event_id": 5}, TypeError, "must be a str"),
    ({**CTX, "schema": "spine-context/2"}, ValueError, "unsupported context schema"),
    (["entity_id"], TypeError, "mapping"),
])
def test_a_malformed_context_is_refused(bad, exc, match):
    with pytest.raises(exc, match=match):
        keyset_content(observe(SICK), context=bad)


def test_binds_checks_a_verdict_issued_against_the_run_bound_keyset():
    keys = observe(SICK)
    verdict = gate.GateResult(gate="g", position=gate.GatePosition.OMEGA, outcome=gate.GateOutcome.PASS,
                              reason="issued for the test", subject=KEYSET_SUBJECT,
                              subject_digest=keyset_digest(keys, context=dict(CTX)))
    assert binds(verdict, keys, context=dict(CTX))
    assert not binds(verdict, keys)
    assert not binds(verdict, keys, context={**CTX, "entity_id": "p2"})
