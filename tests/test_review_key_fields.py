"""Findings of an independent third-party pack author (a cold-chain pack written from the README and the core contract alone).

The registry rebuilt every Key but never looked at the types of its fields, and copied the KeySet's own min_confidence. A pack could return
Key(present="yes", confidence=True) and min_confidence=1.0, and registry.observe accepted it: a truthy string as "present", a bool as a
confidence, and a threshold that hides the pack's own Keys from every lock. Also: a parameter_problems that raised did not name the pack.
"""
import pytest
from zeta import Key, KeySet

from alpha.core import DomainPack, PackError, PackRegistry, Parameter, pack_problems


def good(**over):
    base = dict(name="limit_high", value=10.0, minimum=0.0, maximum=100.0, description="upper limit",
                approved_by="owner", approval_date="2026-11-13", justification="chosen for the test")
    base.update(over)
    return Parameter(**base)


class One(DomainPack):
    NAME = "one_key"
    VERSION = "1.0.0"
    DOMAIN = "testing"
    KEYS = ("k_high",)

    def parameters(self):
        return (good(),)

    def observe(self, raw):
        return KeySet([Key("k_high", present=True, confidence=0.9, reason="x")])


def registered(**over):
    registry = PackRegistry()
    registry.register(type("Variant", (One,), over)())
    return registry


def test_the_honest_pack_passes():
    keys = registered().observe("one_key", 1.0)
    assert keys.min_confidence == 0.0 and keys.get("k_high").confidence == 0.9


@pytest.mark.parametrize("present", ["yes", 1, 0, None, "False"])
def test_a_present_that_is_not_an_exact_bool_is_refused(present):
    registry = registered(observe=lambda self, raw: KeySet([Key("k_high", present=present, reason="x")]))
    with pytest.raises(PackError, match="present"):
        registry.observe("one_key", 1.0)


@pytest.mark.parametrize("confidence", [True, False])
def test_a_confidence_that_is_a_bool_is_refused(confidence):
    registry = registered(observe=lambda self, raw: KeySet([Key("k_high", present=True, confidence=confidence, reason="x")]))
    with pytest.raises(PackError, match="confidence"):
        registry.observe("one_key", 1.0)


def test_a_reason_that_is_not_a_str_is_refused():
    registry = registered(observe=lambda self, raw: KeySet([Key("k_high", present=True, reason=5)]))
    with pytest.raises(PackError, match="reason"):
        registry.observe("one_key", 1.0)


@pytest.mark.parametrize("floor", [1.0, 0.5, 0.01])
def test_a_pack_cannot_raise_the_confidence_floor_to_hide_its_own_keys(floor):
    registry = registered(observe=lambda self, raw: KeySet([Key("k_high", present=True, confidence=0.9, reason="x")], min_confidence=floor))
    with pytest.raises(PackError, match="min_confidence"):
        registry.observe("one_key", 1.0)


def test_a_relation_check_that_raises_names_the_pack():
    class Boom(One):
        def parameter_problems(self, parameters):
            raise RuntimeError("the check failed")

    problems = pack_problems(Boom())
    assert any("one_key" in p and "parameter_problems raised RuntimeError" in p for p in problems), problems
