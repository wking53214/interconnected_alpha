"""Findings of the independent review of the pack contract, each held by a test that fails when its guard is removed.

The review (Opus, high effort, frozen code, 79 attempts) showed that a registered pack could still differ from what the
registry had validated: a name or a Key list read again after the check, a Key set the registry inspected through the pack's
own objects, detector thresholds that were not the registered parameters, a snapshot that shared the pack's objects, and a raw
observation that skipped its own validation at the pack boundary. Each test below is one of those, written to fail on the
code as reviewed.
"""
import dataclasses
import math
import types

import pytest
from zeta import Key, KeySet

from alpha.core import DomainPack, PackError, PackRegistry, PackValidationError, Parameter, pack_problems
from alpha.packs.pediatric_vitals import PediatricVitalsPack, VitalsObservation
from alpha.packs.pediatric_vitals.thresholds import PEDIATRIC_NORMS
from alpha.packs.service_health import ServiceHealthPack, ServiceObservation
from alpha.packs.service_health.thresholds import SERVICE_NORMS


def good(**over):
    base = dict(name="limit_high", value=10.0, minimum=0.0, maximum=100.0, description="upper limit",
                approved_by="owner", approval_date="2026-11-13", justification="chosen for the test")
    base.update(over)
    return Parameter(**base)


class Plain(DomainPack):
    NAME = "plain_pack"
    VERSION = "1.0.0"
    DOMAIN = "testing"
    KEYS = ("k_high",)

    def parameters(self):
        return (good(),)

    def observe(self, raw):
        return KeySet([Key("k_high", present=True, reason="x")])


BAD_SERVICE = ServiceObservation(latency_p95_ms=1500.0, error_rate=0.10, queue_depth=500, tier="interactive")


# ---- H1: the registry reads NAME, VERSION and KEYS once, validates what it read, and keeps that --------------------

def test_a_name_that_answers_differently_on_each_read_cannot_replace_a_registered_pack():
    registry = PackRegistry()
    honest = ServiceHealthPack()
    registry.register(honest)
    reads = []

    class Flip(ServiceHealthPack):
        @property
        def NAME(self):  # noqa: N802
            reads.append(1)
            return "flip_pack" if len(reads) == 1 else "service_health"

    registry.register(Flip())
    assert registry.get("service_health") is honest
    assert registry.names() == ["flip_pack", "service_health"]
    assert registry.identity("flip_pack") == "pack:flip_pack/0.1.0"


def test_a_name_the_validator_refuses_cannot_be_stored_by_changing_on_the_second_read():
    reads = []

    class Late(Plain):
        @property
        def NAME(self):  # noqa: N802
            reads.append(1)
            return "plain_pack" if len(reads) == 1 else "Bad Name!\n"

    registry = PackRegistry()
    registry.register(Late())
    assert registry.names() == ["plain_pack"]


def test_keys_widened_after_registration_are_not_accepted():
    pack = Plain()
    registry = PackRegistry()
    registry.register(pack)
    pack.KEYS = ("k_high", "surprise")
    pack.observe = lambda raw: KeySet([Key("surprise", present=True, reason="late")])
    with pytest.raises(PackError, match="surprise"):
        registry.observe("plain_pack", 1.0)


def test_a_version_changed_after_registration_does_not_change_the_recorded_identity():
    pack = Plain()
    registry = PackRegistry()
    registry.register(pack)
    pack.VERSION = "1.0.0 (approved by someone)\n"
    assert registry.identity("plain_pack") == "pack:plain_pack/1.0.0"


def test_the_identity_of_an_unknown_pack_is_a_named_error():
    with pytest.raises(PackError, match="no pack named"):
        PackRegistry().identity("nowhere")


# ---- H2: the registry rebuilds what a pack returns, from the class's own accessors -------------------------------

def test_a_keyset_that_hides_a_key_from_all_keys_is_still_caught():
    class Hider(Plain):
        def observe(self, raw):
            ks = KeySet([Key("k_high", present=True, reason="x"), Key("surprise", present=True, reason="hidden")])
            ks.all_keys = lambda: (Key("k_high", present=True, reason="x"),)  # shadow the method on the instance
            return ks

    registry = PackRegistry()
    registry.register(Hider())
    with pytest.raises(PackError, match="surprise"):
        registry.observe("plain_pack", 1.0)


def test_a_key_named_with_a_str_subclass_is_refused():
    class Alias(str):
        def __eq__(self, other):
            return other == "k_high" or str.__eq__(self, other)

        __hash__ = str.__hash__

    class Sneaky(Plain):
        def observe(self, raw):
            return KeySet([Key(Alias("k_high"), present=True, reason="x")])

    registry = PackRegistry()
    registry.register(Sneaky())
    with pytest.raises(PackError, match="exact"):
        registry.observe("plain_pack", 1.0)


def test_what_the_registry_returns_is_built_by_the_registry_and_equals_what_the_pack_made():
    returned = []

    class Mark(Plain):
        def observe(self, raw):
            ks = KeySet([Key("k_high", present=True, confidence=0.75, reason="r")], min_confidence=0.5)
            ks.marker = "kept"
            returned.append(ks)
            return ks

    registry = PackRegistry()
    registry.register(Mark())
    out = registry.observe("plain_pack", 1.0)
    assert out is not returned[0] and not hasattr(out, "marker")
    assert out.fingerprint() == returned[0].fingerprint()
    assert out.min_confidence == 0.5


def test_a_key_that_is_not_exactly_a_key_is_refused():
    class Imposter(Key):
        pass

    class Sub(Plain):
        def observe(self, raw):
            return KeySet([Imposter("k_high", present=True, reason="x")])

    registry = PackRegistry()
    registry.register(Sub())
    with pytest.raises(PackError, match="exact"):
        registry.observe("plain_pack", 1.0)


# ---- H3: the thresholds a detector uses are the registered, validated parameters ---------------------------------

def test_the_threshold_tables_cannot_be_changed_in_place():
    with pytest.raises(TypeError):
        PEDIATRIC_NORMS["child"]["hr_high"] = 10000
    with pytest.raises(TypeError):
        PEDIATRIC_NORMS["child"] = {}
    with pytest.raises(TypeError):
        SERVICE_NORMS["interactive"]["error_high"] = 5.0
    with pytest.raises(TypeError):
        SERVICE_NORMS["interactive"] = {}


def test_a_declared_service_threshold_is_the_one_the_detector_uses():
    class Looser(ServiceHealthPack):
        NAME = "looser_service"

        def parameters(self):
            return tuple(dataclasses.replace(p, value=2000.0) if p.name == "interactive_latency_high" else p
                         for p in super().parameters())

    registry = PackRegistry()
    registry.register(Looser())
    declared = {p.name: p.value for p in registry.parameters("looser_service")}
    assert declared["interactive_latency_high"] == 2000.0
    keys = registry.observe("looser_service", BAD_SERVICE)  # 1500 ms is under the declared 2000
    assert "latency_high" not in keys.names_present()
    assert "2000" in keys.get("latency_high").reason


def test_a_declared_pediatric_threshold_is_the_one_the_detector_uses():
    class Looser(PediatricVitalsPack):
        NAME = "looser_pediatric"

        def parameters(self):
            return tuple(dataclasses.replace(p, value=200) if p.name == "child_hr_high" else p for p in super().parameters())

    registry = PackRegistry()
    registry.register(Looser())
    reading = VitalsObservation(heart_rate=180, oxygen_saturation=99.0, respiratory_rate=24, temperature=37.0, age_months=60)
    assert "tachycardia" not in registry.observe("looser_pediatric", reading).names_present()
    stock = PackRegistry()
    stock.register(PediatricVitalsPack())
    assert "tachycardia" in stock.observe("pediatric_vitals", reading).names_present()


# ---- M1: validation lists every problem, even for an integer too large for a float -------------------------------

def test_a_huge_integer_is_a_listed_problem_not_a_crash():
    class Huge(Plain):
        def parameters(self):
            return (good(value=10**400), good(name="other", approved_by=""))

    problems = pack_problems(Huge())
    assert any("limit_high" in p and "finite" in p for p in problems), problems
    assert any("approved_by" in p for p in problems), problems
    with pytest.raises(PackValidationError):
        PackRegistry().register(Huge())


# ---- M2: the snapshot is the registry's own ---------------------------------------------------------------------

def test_changing_a_parameter_object_after_registration_does_not_change_the_snapshot():
    mine = good()

    class Mutable(Plain):
        def parameters(self):
            return (mine,)

    registry = PackRegistry()
    registry.register(Mutable())
    object.__setattr__(mine, "value", math.nan)
    object.__setattr__(mine, "approved_by", "")
    kept = registry.parameters("plain_pack")[0]
    assert kept.value == 10.0 and kept.approved_by == "owner"
    assert kept is not mine


# ---- M3: names and versions are ASCII and end where they end -----------------------------------------------------

@pytest.mark.parametrize("over", [
    {"NAME": "plain_pack\n"}, {"NAME": "plain_pack "}, {"NAME": "plaïn"},
    {"VERSION": "1.0.0\n"}, {"VERSION": "０.１.０"}, {"VERSION": "٠.١.٠"}, {"VERSION": "00.01.000"}, {"VERSION": "01.0.0"},
    {"KEYS": ("k_high\n",)}, {"KEYS": ("k_high ",)}, {"KEYS": ("K_HIGH",)},
])
def test_a_name_version_or_key_name_with_an_invisible_or_non_ascii_part_is_refused(over):
    bad = type("Variant", (Plain,), over)()
    assert pack_problems(bad), over


def test_a_parameter_name_with_a_trailing_newline_is_refused():
    class Newline(Plain):
        def parameters(self):
            return (good(name="limit_high\n"),)

    assert any("name" in p for p in pack_problems(Newline()))


# ---- M4: the pack boundary re-validates the raw observation ------------------------------------------------------

def test_the_service_pack_refuses_what_is_not_exactly_its_observation():
    registry = PackRegistry()
    registry.register(ServiceHealthPack())

    class NoCheck(ServiceObservation):
        def __post_init__(self):
            pass

    for raw in (types.SimpleNamespace(latency_p95_ms=1.0, error_rate=0.0, queue_depth=0, tier="interactive"),
                NoCheck(latency_p95_ms=math.nan, error_rate=0.0, queue_depth=0, tier="interactive"), 5, None):
        with pytest.raises((TypeError, ValueError)):
            registry.observe("service_health", raw)


def test_the_service_pack_refuses_an_observation_edited_after_construction():
    registry = PackRegistry()
    registry.register(ServiceHealthPack())
    raw = ServiceObservation(latency_p95_ms=1.0, error_rate=0.0, queue_depth=0, tier="interactive")
    object.__setattr__(raw, "latency_p95_ms", math.nan)
    with pytest.raises(ValueError):
        registry.observe("service_health", raw)


def test_the_pediatric_pack_refuses_what_is_not_exactly_its_observation_or_was_edited():
    registry = PackRegistry()
    registry.register(PediatricVitalsPack())
    with pytest.raises((TypeError, ValueError)):
        registry.observe("pediatric_vitals", types.SimpleNamespace(heart_rate=1, oxygen_saturation=99.0, respiratory_rate=1,
                                                                   temperature=37.0, age_months=14))
    raw = VitalsObservation(heart_rate=100, oxygen_saturation=99.0, respiratory_rate=24, temperature=37.0, age_months=14)
    object.__setattr__(raw, "heart_rate", math.nan)
    with pytest.raises(ValueError):
        registry.observe("pediatric_vitals", raw)


def test_a_huge_integer_reading_is_a_value_error_not_an_overflow():
    with pytest.raises((TypeError, ValueError)):
        ServiceObservation(latency_p95_ms=10**400, error_rate=0.0, queue_depth=0, tier="interactive")


# ---- M5: guards that were not held by any test -------------------------------------------------------------------

def test_a_parameter_subclass_is_refused():
    class Sub(Parameter):
        pass

    class WithSub(Plain):
        def parameters(self):
            return (Sub(**dataclasses.asdict(good())),)

    assert any("exactly a Parameter" in p for p in pack_problems(WithSub()))


def test_a_real_pack_that_emits_an_undeclared_key_is_refused():
    class Rogue(ServiceHealthPack):
        NAME = "rogue_service"

        def observe(self, raw):
            return KeySet([Key("surprise", present=True, reason="not declared")])

    registry = PackRegistry()
    registry.register(Rogue())
    with pytest.raises(PackError, match="surprise"):
        registry.observe("rogue_service", BAD_SERVICE)
