"""The three Lows the independent review recorded, now held by tests.

L1: each parameter was checked against its own bounds only, so a pack could declare critical latency below high latency.
L2: a pack could emit fewer Keys than it declared, and the registry accepted the shorter set.
L7: VitalsObservation took a bool, a float subclass or any age_months (a negative or a string), unlike ServiceObservation.
"""
import dataclasses

import pytest
from zeta import Key, KeySet

from alpha.core import DomainPack, PackError, PackRegistry, PackValidationError, Parameter, pack_problems
from alpha.packs.pediatric_vitals import PediatricVitalsPack, VitalsObservation
from alpha.packs.service_health import ServiceHealthPack


def good(**over):
    base = dict(name="limit_high", value=10.0, minimum=0.0, maximum=100.0, description="upper limit",
                approved_by="owner", approval_date="2026-11-13", justification="chosen for the test")
    base.update(over)
    return Parameter(**base)


class Two(DomainPack):
    NAME = "two_keys"
    VERSION = "1.0.0"
    DOMAIN = "testing"
    KEYS = ("k_high", "k_low")

    def parameters(self):
        return (good(), good(name="limit_low", value=5.0))

    def observe(self, raw):
        return KeySet([Key("k_high", present=True, reason="x"), Key("k_low", present=False, reason="y")])


# ---- L1: relations between parameters ----------------------------------------------------------------------------

def test_a_pack_can_state_a_relation_between_its_parameters_and_the_registry_enforces_it():
    class Ordered(Two):
        def parameter_problems(self, parameters):
            by_name = {p.name: p.value for p in parameters}
            return [] if by_name["limit_low"] <= by_name["limit_high"] else ["limit_low must not exceed limit_high"]

    PackRegistry().register(Ordered())  # 5 <= 10: fine

    class Crossed(Ordered):
        def parameters(self):
            return (good(), good(name="limit_low", value=50.0))

    assert any("limit_low must not exceed limit_high" in p for p in pack_problems(Crossed()))
    with pytest.raises(PackValidationError, match="limit_low must not exceed"):
        PackRegistry().register(Crossed())


def test_a_relation_check_that_raises_is_a_listed_problem_not_a_crash():
    class Boom(Two):
        def parameter_problems(self, parameters):
            raise RuntimeError("the check failed")

    assert any("parameter_problems" in p and "RuntimeError" in p for p in pack_problems(Boom()))


def test_a_pack_without_relations_is_unchanged():
    assert pack_problems(Two()) == []


def test_critical_latency_below_high_latency_is_refused_in_the_service_pack():
    class Crossed(ServiceHealthPack):
        NAME = "crossed_service"

        def parameters(self):
            return tuple(dataclasses.replace(p, value=100.0) if p.name == "interactive_latency_critical" else p
                         for p in super().parameters())

    with pytest.raises(PackValidationError, match="latency_critical"):
        PackRegistry().register(Crossed())


def test_a_low_heart_rate_limit_above_the_high_one_is_refused_in_the_pediatric_pack():
    class Crossed(PediatricVitalsPack):
        NAME = "crossed_pediatric"

        def parameters(self):
            return tuple(dataclasses.replace(p, value=200) if p.name == "child_hr_low" else p for p in super().parameters())

    with pytest.raises(PackValidationError, match="hr_low"):
        PackRegistry().register(Crossed())


def test_the_shipped_packs_still_register():
    registry = PackRegistry()
    registry.register(ServiceHealthPack())
    registry.register(PediatricVitalsPack())
    assert registry.names() == ["pediatric_vitals", "service_health"]


# ---- L2: every declared Key is emitted ---------------------------------------------------------------------------

def test_a_pack_that_emits_fewer_keys_than_it_declared_is_refused():
    class Short(Two):
        def observe(self, raw):
            return KeySet([Key("k_high", present=True, reason="x")])

    registry = PackRegistry()
    registry.register(Short())
    with pytest.raises(PackError, match="k_low"):
        registry.observe("two_keys", 1.0)


def test_a_pack_that_emits_every_declared_key_passes():
    registry = PackRegistry()
    registry.register(Two())
    assert sorted(k.name for k in KeySet.all_keys(registry.observe("two_keys", 1.0))) == ["k_high", "k_low"]


# ---- L7: VitalsObservation is as strict as ServiceObservation ----------------------------------------------------

GOOD = dict(heart_rate=100, oxygen_saturation=99.0, respiratory_rate=24, temperature=37.0, age_months=14)


@pytest.mark.parametrize("field", ["heart_rate", "oxygen_saturation", "respiratory_rate", "temperature"])
@pytest.mark.parametrize("bad", [True, False, "100", None, b"1"])
def test_a_vital_that_is_not_an_exact_int_or_float_is_refused(field, bad):
    with pytest.raises((TypeError, ValueError)):
        VitalsObservation(**{**GOOD, field: bad})


def test_a_float_subclass_is_refused():
    class F(float):
        pass

    with pytest.raises(TypeError):
        VitalsObservation(**{**GOOD, "heart_rate": F(100.0)})


@pytest.mark.parametrize("age", [True, False, -1, 3.5, "5", float("nan")])
def test_an_age_that_is_not_none_or_a_non_negative_exact_int_is_refused(age):
    with pytest.raises((TypeError, ValueError)):
        VitalsObservation(**{**GOOD, "age_months": age})


@pytest.mark.parametrize("age", [None, 0, 2, 14, 100])
def test_an_honest_age_is_accepted(age):
    assert VitalsObservation(**{**GOOD, "age_months": age}).age_months == age


def test_a_huge_integer_vital_is_a_value_error_not_an_overflow():
    with pytest.raises((TypeError, ValueError)):
        VitalsObservation(**{**GOOD, "heart_rate": 10**400})
