"""alpha records, when asked, an origin claim for its readings, bound into the digest.

The origin is the producer's own assertion. These tests cover well-formedness, snapshotting and binding; nothing
here (or in alpha) authenticates the claim or checks that it is true.
"""
import os
from collections.abc import Mapping

import pytest

if os.environ.get("ALPHA_REQUIRE_CNS") == "1":  # CI: a missing cns is a failure, not a skip
    import cns.gate as gate
else:
    gate = pytest.importorskip("cns.gate")

from alpha import VitalsObservation, observe  # noqa: E402
from alpha.cns_connector import CONTEXT_SCHEMA, KEYSET_SUBJECT, binds, keyset_content, keyset_digest  # noqa: E402

CTX = {"schema": CONTEXT_SCHEMA, "entity_id": "p1", "event_id": "ev-1", "run_id": "run-1"}
ORIGIN = {
    "source": "bedside-monitor-7",
    "producer": "ward-integration-service",
    "observed_at": "2026-01-02T03:04:05+00:00",
    "collection_context": "routine overnight observation",
    "transformation": "none, values as read",
}
SICK = VitalsObservation(heart_rate=148, oxygen_saturation=90.0, respiratory_rate=36, temperature=39.6, age_months=14)


def test_content_without_origin_is_unchanged_and_digests_match():
    keys = observe(SICK)
    assert "origin" not in keyset_content(keys)
    assert "origin" not in keyset_content(keys, context=dict(CTX))
    assert keyset_content(keys, origin=None) == keyset_content(keys)
    assert keyset_digest(keys, origin=None) == keyset_digest(keys)
    assert keyset_digest(keys, context=dict(CTX), origin=None) == keyset_digest(keys, context=dict(CTX))
    # the digest of the pre-change content shape: exactly {min_confidence, keys} hashed by the gate
    assert keyset_digest(keys) == gate.subject_digest({"min_confidence": keys.min_confidence, "keys": keyset_content(keys)["keys"]})


def test_origin_is_included_under_origin_and_changes_the_digest():
    keys = observe(SICK)
    content = keyset_content(keys, context=dict(CTX), origin=dict(ORIGIN))
    assert content["origin"] == ORIGIN
    assert keyset_digest(keys, context=dict(CTX), origin=ORIGIN) != keyset_digest(keys, context=dict(CTX))


@pytest.mark.parametrize("field", sorted(ORIGIN))
def test_changing_any_origin_field_changes_the_digest(field):
    keys = observe(SICK)
    other = dict(ORIGIN)
    other[field] = "2026-01-02T03:04:06+00:00" if field == "observed_at" else other[field] + " (changed)"
    assert keyset_digest(keys, origin=other) != keyset_digest(keys, origin=ORIGIN)


def test_origin_works_without_a_context_and_with_one():
    keys = observe(SICK)
    assert keyset_content(keys, origin=ORIGIN)["origin"] == ORIGIN
    assert "context" not in keyset_content(keys, origin=ORIGIN)


def test_a_non_mapping_origin_is_a_type_error():
    with pytest.raises(TypeError, match="origin"):
        keyset_content(observe(SICK), origin=["source"])


@pytest.mark.parametrize("field", sorted(ORIGIN))
def test_a_wrong_type_names_the_field(field):
    bad = dict(ORIGIN)
    bad[field] = 7
    with pytest.raises(TypeError, match=field):
        keyset_content(observe(SICK), origin=bad)


@pytest.mark.parametrize("field", sorted(ORIGIN))
def test_a_str_subclass_names_the_field(field):
    class S(str):
        pass

    bad = dict(ORIGIN)
    bad[field] = S(bad[field])
    with pytest.raises(TypeError, match=field):
        keyset_content(observe(SICK), origin=bad)


@pytest.mark.parametrize("field", sorted(ORIGIN))
def test_an_empty_field_names_the_field(field):
    bad = dict(ORIGIN)
    bad[field] = ""
    with pytest.raises(ValueError, match=field):
        keyset_content(observe(SICK), origin=bad)


@pytest.mark.parametrize("field", sorted(ORIGIN))
def test_a_missing_field_is_named(field):
    bad = {k: v for k, v in ORIGIN.items() if k != field}
    with pytest.raises(ValueError, match=field):
        keyset_content(observe(SICK), origin=bad)


def test_an_extra_key_is_refused_and_named():
    with pytest.raises(ValueError, match="verified_by"):
        keyset_content(observe(SICK), origin={**ORIGIN, "verified_by": "me"})


@pytest.mark.parametrize("text", ["yesterday", "2026-13-45", "12:00 on Tuesday", "2026-01-02T25:00:00"])
def test_observed_at_must_parse_as_iso_8601(text):
    with pytest.raises(ValueError, match="observed_at"):
        keyset_content(observe(SICK), origin={**ORIGIN, "observed_at": text})


def test_observed_at_accepts_date_only_and_offset_forms():
    for text in ("2026-01-02", "2026-01-02T03:04:05", "2026-01-02T03:04:05+02:00"):
        assert keyset_content(observe(SICK), origin={**ORIGIN, "observed_at": text})["origin"]["observed_at"] == text


def test_the_origin_is_snapshotted_once():
    class Shifting(Mapping):
        def __init__(self):
            self.reads = 0

        def __iter__(self):
            return iter(ORIGIN)

        def __len__(self):
            return len(ORIGIN)

        def __getitem__(self, key):
            self.reads += 1
            return ORIGIN[key] if self.reads <= len(ORIGIN) else ""

    assert keyset_content(observe(SICK), origin=Shifting())["origin"] == ORIGIN


def test_the_origin_in_the_content_is_a_copy():
    source = dict(ORIGIN)
    content = keyset_content(observe(SICK), origin=source)
    source["source"] = "changed later"
    assert content["origin"] == ORIGIN


def _verdict(keys, **kw):
    return gate.GateResult(
        gate="test",
        position=gate.GatePosition.OMEGA,
        outcome=gate.GateOutcome.PASS,
        subject=KEYSET_SUBJECT,
        subject_digest=keyset_digest(keys, **kw),
    )


def test_a_verdict_binds_to_the_origin_it_was_issued_against_and_to_no_other():
    keys = observe(SICK)
    result = _verdict(keys, context=dict(CTX), origin=ORIGIN)
    assert binds(result, keys, context=dict(CTX), origin=ORIGIN)
    assert not binds(result, keys, context=dict(CTX))
    assert not binds(result, keys, context=dict(CTX), origin={**ORIGIN, "producer": "someone else"})
    assert not binds(_verdict(keys, context=dict(CTX)), keys, context=dict(CTX), origin=ORIGIN)
