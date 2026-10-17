"""alpha's detected Keys made bindable to a CNS verdict (binding only, no gate).

These skip where ``cns`` is not installed. CI installs the extra and sets
ALPHA_REQUIRE_CNS=1, so there they cannot skip.
"""
import os

import pytest

if os.environ.get("ALPHA_REQUIRE_CNS") == "1":  # CI: a missing cns is a failure, not a skip
    import cns.gate as gate
else:
    gate = pytest.importorskip("cns.gate")

from alpha import VitalsObservation, observe  # noqa: E402
from alpha.cns_connector import KEYSET_SUBJECT, binds, keyset_content, keyset_digest  # noqa: E402
from zeta import Key, KeySet, LockState  # noqa: E402


def issued(subject, digest):
    """A verdict as a gate would issue it: bound to what it judged. The outcome is irrelevant to binding."""
    return gate.GateResult(gate="test", position=gate.GatePosition.OMEGA, outcome=gate.GateOutcome.PASS,
                           subject=subject, subject_digest=digest)


def hand_built():
    return gate.GateResult(gate="test", position=gate.GatePosition.OMEGA, outcome=gate.GateOutcome.PASS)


def vitals(**over):
    base = dict(heart_rate=145, oxygen_saturation=90.0, respiratory_rate=36, temperature=39.6, age_months=48)
    base.update(over)
    return VitalsObservation(**base)


def a_keyset(**over):
    spec = dict(name="fever", present=True, confidence=0.75, reason="Temp 39.6 vs threshold 39.5")
    spec.update(over.pop("key", {}))
    keys = [Key(**spec), Key(name="tachycardia", present=False, confidence=1.0, reason="HR 100 vs threshold 130")]
    return KeySet(keys, **over)


# ------------------------------------------------------------ content shape

def test_the_content_names_every_key_field_and_the_threshold_sorted_by_name():
    assert keyset_content(a_keyset(min_confidence=0.5)) == {
        "min_confidence": 0.5,
        "keys": [
            {"name": "fever", "present": True, "confidence": 0.75, "reason": "Temp 39.6 vs threshold 39.5"},
            {"name": "tachycardia", "present": False, "confidence": 1.0, "reason": "HR 100 vs threshold 130"}]}


def test_content_is_json_like_and_cns_accepts_it():
    for ks in (a_keyset(), KeySet([]), observe(vitals())):
        content = keyset_content(ks)
        assert isinstance(gate.subject_digest(content), str)
        assert type(content["min_confidence"]) is float and isinstance(content["keys"], list)
        for key in content["keys"]:
            assert set(key) == {"name", "present", "confidence", "reason"}
            assert type(key["name"]) is str and type(key["present"]) is bool
            assert type(key["confidence"]) is float and type(key["reason"]) is str


def test_the_digest_is_cns_subject_digest_of_the_content():
    ks = observe(vitals())
    assert keyset_digest(ks) == gate.subject_digest(keyset_content(ks))


# ------------------------------------------------------------ determinism and irrelevant differences

def test_the_digest_is_deterministic_across_equal_but_distinct_objects():
    one, two = observe(vitals()), observe(vitals())
    assert one is not two and keyset_digest(one) == keyset_digest(two)
    assert keyset_digest(a_keyset()) == keyset_digest(a_keyset())


def test_the_order_keys_were_added_in_cannot_change_the_digest():
    keys = [Key("a", True, reason="r1"), Key("b", False, reason="r2"), Key("c", True, 0.5, "r3")]
    forward, backward = KeySet(keys), KeySet(list(reversed(keys)))
    assert list(forward._by_name) != list(backward._by_name)
    assert keyset_digest(forward) == keyset_digest(backward)


def test_a_confidence_given_as_an_int_is_the_same_record_as_the_float():
    assert keyset_digest(KeySet([Key("a", True, 1)])) == keyset_digest(KeySet([Key("a", True, 1.0)]))
    assert keyset_digest(KeySet([Key("a", True)], min_confidence=0)) == keyset_digest(KeySet([Key("a", True)], min_confidence=0.0))
    assert keyset_digest(KeySet([Key("a", 1)])) == keyset_digest(KeySet([Key("a", True)]))


def test_a_key_added_twice_is_one_key_as_the_keyset_defines_it():
    twice = KeySet([Key("a", False, reason="old"), Key("a", True, reason="new")])
    assert keyset_digest(twice) == keyset_digest(KeySet([Key("a", True, reason="new")]))


# ------------------------------------------------------------ every bound field matters

@pytest.mark.parametrize("key_over", [
    {"name": "hypothermia"}, {"present": False}, {"confidence": 0.5}, {"confidence": 1.0},
    {"reason": "Temp 39.6 vs threshold 39.6"}, {"reason": ""}])
def test_changing_any_key_field_changes_the_digest(key_over):
    assert keyset_digest(a_keyset(key=key_over)) != keyset_digest(a_keyset())


def test_changing_min_confidence_changes_the_digest():
    assert keyset_digest(a_keyset(min_confidence=0.9)) != keyset_digest(a_keyset())
    assert keyset_digest(a_keyset(min_confidence=0.1)) != keyset_digest(a_keyset(min_confidence=0.2))


def test_adding_or_removing_a_key_changes_the_digest():
    base = a_keyset()
    extra = KeySet([base.get("fever"), base.get("tachycardia"), Key("bradycardia", False, 1.0, "r")])
    only_one = KeySet([base.get("fever")])
    assert len({keyset_digest(base), keyset_digest(extra), keyset_digest(only_one), keyset_digest(KeySet([]))}) == 4


def test_which_key_holds_which_value_matters():
    one = KeySet([Key("a", True, reason="x"), Key("b", False, reason="y")])
    two = KeySet([Key("a", False, reason="x"), Key("b", True, reason="y")])
    swapped_reasons = KeySet([Key("a", True, reason="y"), Key("b", False, reason="x")])
    assert len({keyset_digest(one), keyset_digest(two), keyset_digest(swapped_reasons)}) == 3


# ------------------------------------------------------------ wrong types

@pytest.mark.parametrize("bad", [None, "keys", {"fever": True}, [Key("a", True)], {Key("a", True)}, Key("a", True),
                                 LockState(), vitals(), 7])
def test_something_that_is_not_a_keyset_is_a_type_error(bad):
    with pytest.raises(TypeError):
        keyset_content(bad)
    with pytest.raises(TypeError):
        keyset_digest(bad)
    with pytest.raises(TypeError):
        binds(issued(KEYSET_SUBJECT, "d"), bad)


def test_a_keyset_holding_something_that_is_not_a_key_is_a_type_error():
    ks = KeySet([Key("a", True)])
    ks._by_name["b"] = ("b", True)
    with pytest.raises(TypeError):
        keyset_content(ks)


@pytest.mark.parametrize("bad", [{"name": 7}, {"reason": None}, {"reason": 5}])
def test_a_key_with_unbindable_text_is_a_type_error(bad):
    spec = dict(name="a", present=True, confidence=1.0, reason="r")
    spec.update(bad)
    with pytest.raises(TypeError):
        keyset_content(KeySet([Key(**spec)]))


# ------------------------------------------------------------ binds

def test_a_verdict_issued_against_a_keyset_binds_to_that_keyset_only():
    ks = a_keyset()
    verdict = issued(KEYSET_SUBJECT, keyset_digest(ks))
    assert binds(verdict, ks)
    assert binds(verdict, a_keyset())                                      # equal, not the same object
    assert not binds(verdict, a_keyset(key={"present": False}))
    assert not binds(verdict, a_keyset(min_confidence=0.5))
    assert not binds(verdict, KeySet([]))


def test_binds_checks_the_subject_not_just_the_digest():
    ks = a_keyset()
    digest = keyset_digest(ks)
    assert not binds(issued("some.other.subject", digest), ks)
    assert binds(issued("some.other.subject", digest), ks, subject="some.other.subject")
    assert not binds(issued(KEYSET_SUBJECT, digest), ks, subject="some.other.subject")


def test_binds_checks_the_digest_not_just_the_subject():
    assert not binds(issued(KEYSET_SUBJECT, "0" * 64), a_keyset())
    assert not binds(issued(KEYSET_SUBJECT, keyset_digest(KeySet([]))), a_keyset())


def test_an_unbound_or_hand_built_verdict_binds_to_nothing():
    assert not binds(hand_built(), a_keyset())
    assert not binds(hand_built(), KeySet([]), subject="")
    assert not binds(issued("", keyset_digest(a_keyset())), a_keyset(), subject="")
    assert not binds(issued(KEYSET_SUBJECT, ""), a_keyset())


def test_binds_returns_a_real_bool():
    assert binds(issued(KEYSET_SUBJECT, keyset_digest(a_keyset())), a_keyset()) is True
    assert binds(hand_built(), a_keyset()) is False


# ------------------------------------------------------------ against the real detectors

def test_a_verdict_on_really_detected_keys_binds_to_them_and_not_to_other_vitals():
    ks = observe(vitals())
    assert ks.is_present("septic_shock") and ks.is_present("fever")
    verdict = issued(KEYSET_SUBJECT, keyset_digest(ks))
    assert binds(verdict, ks)
    assert binds(verdict, observe(vitals()))                               # detected again from the same vitals
    assert not binds(verdict, observe(vitals(heart_rate=100)))             # tachycardia and septic_shock flip
    assert not binds(verdict, observe(vitals(oxygen_saturation=98.0)))


def test_the_bound_reason_text_carries_the_readings_so_a_reading_change_is_a_new_record():
    one, two = observe(vitals(heart_rate=145)), observe(vitals(heart_rate=146))
    assert one.names_present() == two.names_present()                      # the same keys fire...
    assert keyset_digest(one) != keyset_digest(two)                        # ...on a different reading


def test_every_detector_key_is_in_the_bound_content():
    ks = observe(vitals())
    content = keyset_content(ks)
    names = [k["name"] for k in content["keys"]]
    assert names == sorted(names) and len(names) == len(set(names)) == 10
    assert {k["name"] for k in content["keys"] if k["present"]} == ks.names_present()
    for entry in content["keys"]:
        key = ks.get(entry["name"])
        assert (entry["present"], entry["confidence"], entry["reason"]) == (key.present, key.confidence, key.reason)
    assert binds(issued(KEYSET_SUBJECT, gate.subject_digest(content)), ks)


@pytest.mark.parametrize("age", [None, 3, 14, 48, 120, 200])
def test_real_detection_is_bindable_at_every_age_group(age):
    ks = observe(vitals(age_months=age))
    assert binds(issued(KEYSET_SUBJECT, keyset_digest(ks)), ks)


def test_the_keys_come_from_the_public_listing_not_the_private_index():
    class Listed(KeySet):
        def all_keys(self):
            return (Key("listed", True, 0.5, "from all_keys"),)

    content = keyset_content(Listed([Key("indexed", True)]))
    assert [k["name"] for k in content["keys"]] == ["listed"]
