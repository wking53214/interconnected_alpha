"""The public API of alpha and alpha.core, pinned.

A pack author imports these names and subclasses or calls these methods. Anything added, removed or renamed here is a change to what a
third-party pack can rely on, so it must be a deliberate edit of this file, in the same commit, with a reason, not a side effect.
"""
import dataclasses
import inspect

import alpha
import alpha.core as core
from alpha.core import DomainPack, PackError, PackRegistry, PackValidationError, Parameter, pack_identity

EXPORTS = ["DomainPack", "PackError", "PackRegistry", "PackValidationError", "Parameter", "pack_identity", "pack_problems", "validate_pack"]


def public(cls):
    return sorted(name for name in vars(cls) if not name.startswith("_"))


def arguments(function):
    return list(inspect.signature(function).parameters)


def test_the_package_root_exports_exactly_the_core_api():
    assert sorted(alpha.__all__) == EXPORTS
    assert all(hasattr(alpha, name) for name in EXPORTS)


def test_the_core_exports_exactly_the_same_names():
    assert sorted(core.__all__) == EXPORTS
    assert all(getattr(alpha, name) is getattr(core, name) for name in EXPORTS)


def test_the_root_exports_no_domain_type():
    for name in ("VitalsObservation", "ServiceObservation", "observe", "PEDIATRIC_NORMS", "detect_all"):
        assert not hasattr(alpha, name)


def test_a_pack_author_sees_exactly_these_methods():
    assert public(DomainPack) == ["identity", "observe", "parameter_problems", "parameters"]
    assert DomainPack.__abstractmethods__ == frozenset({"observe", "parameters"})
    assert arguments(DomainPack.observe) == ["self", "raw"]
    assert arguments(DomainPack.parameters) == ["self"]
    assert arguments(DomainPack.parameter_problems) == ["self", "parameters"]


def test_the_registry_offers_exactly_these_methods():
    assert public(PackRegistry) == ["get", "identity", "names", "observe", "parameters", "register"]
    assert arguments(PackRegistry.register) == ["self", "pack"]
    assert arguments(PackRegistry.get) == ["self", "name"]
    assert arguments(PackRegistry.identity) == ["self", "name"]
    assert arguments(PackRegistry.parameters) == ["self", "name"]
    assert arguments(PackRegistry.names) == ["self"]
    assert arguments(PackRegistry.observe) == ["self", "name", "raw"]


def test_a_parameter_has_exactly_these_fields_in_this_order():
    assert [f.name for f in dataclasses.fields(Parameter)] == [
        "name", "value", "minimum", "maximum", "description", "approved_by", "approval_date", "justification"]
    assert Parameter.__dataclass_params__.frozen is True


def test_the_errors_keep_their_hierarchy():
    assert issubclass(PackValidationError, PackError) and issubclass(PackError, Exception)
    assert hasattr(PackValidationError(["problem"]), "problems")


def test_the_identity_format_is_stable():
    class P(DomainPack):
        NAME, VERSION, DOMAIN, KEYS = "some_pack", "1.2.3", "d", ("k",)

        def parameters(self):
            return ()

        def observe(self, raw):
            raise NotImplementedError

    assert pack_identity(P()) == "pack:some_pack/1.2.3" and P().identity() == "pack:some_pack/1.2.3"
