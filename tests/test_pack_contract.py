"""The domain-pack contract (alpha.core): what a pack must declare, how it is validated, and how a registry admits it.

Modelled on sentinel_os's cassettes: a domain-blind kernel contract, parameters declared as named, typed, bounded data
with approval metadata and no defaults, total fail-loud validation on the load path, and the pack's identity available to
record with a decision. Nothing here is domain-specific: the packs below are fakes.
"""
import re
from pathlib import Path

import pytest
from zeta import Key, KeySet

from alpha.core import (
    DomainPack,
    PackError,
    PackRegistry,
    PackValidationError,
    Parameter,
    pack_identity,
    pack_problems,
)

ROOT = Path(__file__).resolve().parents[1]


def good_parameter(**over):
    base = dict(name="limit_high", value=10.0, minimum=0.0, maximum=100.0, description="upper limit of the reading",
                approved_by="owner", approval_date="2026-11-13", justification="chosen for the test")
    base.update(over)
    return Parameter(**base)


class FakePack(DomainPack):
    NAME = "fake_domain"
    VERSION = "1.2.3"
    DOMAIN = "testing"
    KEYS = ("reading_high", "reading_low")

    def parameters(self):
        return (good_parameter(),)

    def observe(self, raw):
        limit = self.parameters()[0].value
        return KeySet([Key("reading_high", present=raw > limit, reason=f"{raw} against {limit}"),
                       Key("reading_low", present=raw < 0, reason=f"{raw} below zero")])


def pack_with(**over):
    """A FakePack subclass with class attributes or methods replaced."""
    return type("Variant", (FakePack,), over)()


# ---- the honest path --------------------------------------------------------------------------------------------

def test_a_valid_pack_registers_and_observes():
    registry = PackRegistry()
    registry.register(FakePack())
    assert registry.names() == ["fake_domain"]
    keys = registry.observe("fake_domain", 50.0)
    assert isinstance(keys, KeySet) and "reading_high" in keys.names_present()


def test_the_identity_names_the_pack_and_its_version():
    assert pack_identity(FakePack()) == "pack:fake_domain/1.2.3"
    assert FakePack().identity() == "pack:fake_domain/1.2.3"


def test_a_valid_pack_has_no_problems():
    assert pack_problems(FakePack()) == []


# ---- the contract is total: every violation is named, together --------------------------------------------------

def test_every_violation_is_reported_together_not_just_the_first():
    bad = pack_with(NAME="Bad Name", VERSION="one", DOMAIN="", KEYS=("a", "a"),
                    parameters=lambda self: (good_parameter(value=500.0), good_parameter(name="limit_high", approved_by="")))
    problems = pack_problems(bad)
    joined = "\n".join(problems)
    for expected in ("NAME", "VERSION", "DOMAIN", "KEYS", "limit_high", "approved_by"):
        assert expected in joined, expected
    assert len(problems) >= 6
    with pytest.raises(PackValidationError) as info:
        PackRegistry().register(bad)
    assert info.value.problems == problems


@pytest.mark.parametrize("over, fragment", [
    ({"NAME": "UPPER"}, "NAME"),
    ({"NAME": ""}, "NAME"),
    ({"NAME": 7}, "NAME"),
    ({"VERSION": "1.2"}, "VERSION"),
    ({"VERSION": "1.2.3-beta"}, "VERSION"),
    ({"DOMAIN": ""}, "DOMAIN"),
    ({"DOMAIN": None}, "DOMAIN"),
    ({"KEYS": ()}, "KEYS"),
    ({"KEYS": ["reading_high"]}, "KEYS"),
    ({"KEYS": ("reading_high", "reading_high")}, "KEYS"),
    ({"KEYS": ("reading_high", "")}, "KEYS"),
])
def test_a_malformed_identity_or_key_declaration_is_refused(over, fragment):
    problems = pack_problems(pack_with(**over))
    assert problems and any(fragment in p for p in problems), problems


# ---- parameters: named, typed, bounded, approved, with no defaults -----------------------------------------------

@pytest.mark.parametrize("over, fragment", [
    ({"value": 101.0}, "outside"),
    ({"value": -0.5}, "outside"),
    ({"value": float("nan")}, "finite"),
    ({"value": float("inf")}, "finite"),
    ({"value": True}, "exact int or float"),
    ({"value": "10"}, "exact int or float"),
    ({"minimum": 50.0, "maximum": 10.0}, "minimum"),
    ({"name": "Limit"}, "name"),
    ({"description": ""}, "description"),
    ({"approved_by": ""}, "approved_by"),
    ({"justification": ""}, "justification"),
    ({"approval_date": "13 November 2026"}, "approval_date"),
    ({"approval_date": "2026-13-45"}, "approval_date"),
])
def test_a_parameter_that_is_out_of_bounds_untyped_or_unapproved_is_refused(over, fragment):
    pack = pack_with(parameters=lambda self: (good_parameter(**over),))
    problems = pack_problems(pack)
    assert problems and any(fragment in p for p in problems), problems


def test_parameter_names_must_be_unique():
    pack = pack_with(parameters=lambda self: (good_parameter(), good_parameter(value=20.0)))
    assert any("limit_high" in p and "twice" in p for p in pack_problems(pack))


def test_a_string_subclass_is_not_a_string_for_the_contract():
    class Sneaky(str):
        pass

    assert pack_problems(pack_with(NAME=Sneaky("fake_domain")))
    assert pack_problems(pack_with(parameters=lambda self: (good_parameter(approved_by=Sneaky("owner")),)))


def test_parameters_must_be_a_tuple_of_parameter():
    assert pack_problems(pack_with(parameters=lambda self: [good_parameter()]))
    assert pack_problems(pack_with(parameters=lambda self: (good_parameter(), "not a parameter")))


def test_a_pack_that_does_not_implement_observe_cannot_be_built():
    class NoObserve(DomainPack):
        NAME, VERSION, DOMAIN, KEYS = "x", "1.0.0", "d", ("k",)

        def parameters(self):
            return ()

    with pytest.raises(TypeError):
        NoObserve()


# ---- the registry: fail-loud load, no defaults, no overwrite -----------------------------------------------------

def test_an_invalid_pack_is_not_registered():
    registry = PackRegistry()
    with pytest.raises(PackValidationError):
        registry.register(pack_with(VERSION="x"))
    assert registry.names() == []


def test_a_name_cannot_be_registered_twice_even_at_another_version():
    registry = PackRegistry()
    registry.register(FakePack())
    with pytest.raises(PackError, match="already registered"):
        registry.register(pack_with(VERSION="2.0.0"))
    assert registry.get("fake_domain").VERSION == "1.2.3"


def test_an_unknown_pack_is_a_named_error_not_a_default():
    with pytest.raises(PackError, match="no pack named 'nowhere'"):
        PackRegistry().get("nowhere")
    with pytest.raises(PackError):
        PackRegistry().observe("nowhere", 1.0)


def test_a_non_pack_is_refused():
    with pytest.raises(PackValidationError):
        PackRegistry().register(object())  # type: ignore[arg-type]


def test_the_parameters_are_snapshotted_at_registration():
    calls = []

    class Drifting(FakePack):
        def parameters(self):
            calls.append(1)
            return (good_parameter(value=10.0 if len(calls) == 1 else 999.0),)

    registry = PackRegistry()
    registry.register(Drifting())
    assert registry.parameters("fake_domain")[0].value == 10.0
    assert registry.parameters("fake_domain")[0].value == 10.0  # not re-read from the pack


# ---- what a pack may return --------------------------------------------------------------------------------------

def test_a_pack_that_returns_something_other_than_a_keyset_is_refused():
    registry = PackRegistry()
    registry.register(pack_with(observe=lambda self, raw: {"reading_high": True}))
    with pytest.raises(PackError, match="KeySet"):
        registry.observe("fake_domain", 1.0)


def test_a_keyset_subclass_is_refused():
    class MyKeySet(KeySet):
        pass

    registry = PackRegistry()
    registry.register(pack_with(observe=lambda self, raw: MyKeySet([Key("reading_high", present=True, reason="x")])))
    with pytest.raises(PackError, match="KeySet"):
        registry.observe("fake_domain", 1.0)


def test_a_pack_may_not_emit_a_key_it_did_not_declare():
    registry = PackRegistry()
    registry.register(pack_with(observe=lambda self, raw: KeySet([Key("surprise", present=True, reason="undeclared")])))
    with pytest.raises(PackError, match="surprise"):
        registry.observe("fake_domain", 1.0)


def test_an_exception_from_a_pack_is_not_swallowed():
    registry = PackRegistry()

    def boom(self, raw):
        raise ZeroDivisionError("the pack failed")

    registry.register(pack_with(observe=boom))
    with pytest.raises(ZeroDivisionError):
        registry.observe("fake_domain", 1.0)


# ---- the core stays domain-neutral -------------------------------------------------------------------------------

CLINICAL = re.compile(r"patient|vital|pediatric|paediatric|sepsis|tachy|fever|oxygen|heart|clinical|age_months|neonat|infant",
                      re.IGNORECASE)


OPERATIONS = re.compile(r"latency|queue|backlog|outage|error[ _]rate|service[ _]health|degraded", re.IGNORECASE)


def test_the_core_names_no_domain():
    """Neither pack's vocabulary appears in the core or the package root: a test for one domain only would pass a core that names the other."""
    offenders = []
    for path in sorted((ROOT / "alpha" / "core").glob("*.py")) + [ROOT / "alpha" / "__init__.py"]:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if CLINICAL.search(line) or OPERATIONS.search(line):
                offenders.append(f"{path.name}:{number}: {line.strip()}")
    assert not offenders, offenders


def test_the_package_list_includes_the_core():
    assert '"alpha.core"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
