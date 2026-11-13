"""The service-health pack: a second domain, unrelated to medicine, written against the same contract.

It exists to show that alpha's core is not pediatric in disguise: raw observations of a running service (p95 latency, error rate,
queue depth, a tier) become named Keys, with thresholds declared as bounded parameters from the start. The values are synthetic
and tuned to no real service.
"""
import re
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from alpha.core import PackRegistry, pack_identity, pack_problems
from alpha.packs.service_health import (
    ALL_DETECTORS,
    PARAMETERS,
    SERVICE_NORMS,
    ServiceHealthPack,
    ServiceObservation,
    detect_all,
    observe,
)

ROOT = Path(__file__).resolve().parents[1]
EPS = 1e-6


def obs(**over):
    base = dict(latency_p95_ms=120.0, error_rate=0.001, queue_depth=5, tier="interactive")
    base.update(over)
    return ServiceObservation(**base)


def present(keys):
    return set(keys.names_present())


# ---- the detectors, at and around their thresholds ---------------------------------------------------------------

def test_a_healthy_service_has_no_key_present():
    assert present(observe(obs())) == set()


@pytest.mark.parametrize("tier", ["interactive", "batch"])
@pytest.mark.parametrize("field, column, key", [
    ("latency_p95_ms", "latency_high", "latency_high"),
    ("latency_p95_ms", "latency_critical", "latency_critical"),
    ("error_rate", "error_high", "error_burst"),
    ("queue_depth", "queue_high", "queue_backlog"),
])
def test_a_key_is_absent_at_its_threshold_and_present_just_above_it(tier, field, column, key):
    threshold = SERVICE_NORMS[tier][column]
    assert key not in present(observe(obs(tier=tier, **{field: threshold})))
    assert key in present(observe(obs(tier=tier, **{field: threshold + EPS})))


def test_the_interactive_numbers_are_the_documented_ones():
    assert SERVICE_NORMS["interactive"] == {"latency_high": 300.0, "latency_critical": 1000.0, "error_high": 0.02, "queue_high": 100.0}
    assert SERVICE_NORMS["batch"] == {"latency_high": 5000.0, "latency_critical": 30000.0, "error_high": 0.05, "queue_high": 10000.0}


def test_the_same_latency_is_high_for_an_interactive_service_and_fine_for_a_batch_job():
    assert "latency_high" in present(observe(obs(latency_p95_ms=2000.0, tier="interactive")))
    assert "latency_high" not in present(observe(obs(latency_p95_ms=2000.0, tier="batch")))


def test_critical_latency_is_also_high_latency():
    assert {"latency_high", "latency_critical"} <= present(observe(obs(latency_p95_ms=5000.0)))


def test_degraded_service_needs_high_latency_and_an_error_burst_together():
    assert "degraded_service" not in present(observe(obs(latency_p95_ms=500.0)))
    assert "degraded_service" not in present(observe(obs(error_rate=0.5)))
    assert "degraded_service" in present(observe(obs(latency_p95_ms=500.0, error_rate=0.5)))


def test_every_key_carries_confidence_one_and_a_reason_naming_the_reading():
    keys = detect_all(obs(latency_p95_ms=500.0, error_rate=0.5, queue_depth=500))
    assert [k.confidence for k in keys] == [1.0] * len(keys)
    assert all(k.reason.strip() for k in keys)
    by_name = {k.name: k for k in keys}
    assert "500.0" in by_name["latency_high"].reason and "300.0" in by_name["latency_high"].reason


def test_detector_names_are_unique_and_are_the_packs_declared_keys():
    names = [detector(obs()).name for detector in ALL_DETECTORS]
    assert len(names) == len(set(names)) == 5
    assert tuple(names) == ServiceHealthPack.KEYS


# ---- the observation is validated where raw data enters ---------------------------------------------------------

@pytest.mark.parametrize("over", [
    {"latency_p95_ms": -1.0},
    {"latency_p95_ms": float("nan")},
    {"latency_p95_ms": float("inf")},
    {"error_rate": -0.01},
    {"error_rate": 1.01},
    {"error_rate": float("nan")},
    {"queue_depth": -1},
    {"queue_depth": float("inf")},
    {"tier": "other"},
    {"tier": ""},
])
def test_an_impossible_observation_is_refused_at_construction(over):
    with pytest.raises(ValueError):
        obs(**over)


@pytest.mark.parametrize("over", [
    {"latency_p95_ms": True},
    {"latency_p95_ms": "120"},
    {"latency_p95_ms": None},
    {"error_rate": False},
    {"queue_depth": "5"},
    {"queue_depth": None},
    {"tier": 7},
    {"tier": None},
])
def test_a_reading_of_the_wrong_type_is_refused_not_coerced(over):
    with pytest.raises(TypeError):
        obs(**over)


def test_an_observation_is_immutable():
    o = obs()
    with pytest.raises(FrozenInstanceError):
        o.error_rate = 0.5  # type: ignore[misc]


def test_a_str_subclass_tier_is_not_a_tier():
    class T(str):
        pass

    with pytest.raises(TypeError):
        obs(tier=T("interactive"))


# ---- the pack ----------------------------------------------------------------------------------------------------

def test_the_pack_keeps_the_contract_and_registers():
    pack = ServiceHealthPack()
    assert pack_problems(pack) == []
    registry = PackRegistry()
    registry.register(pack)
    assert registry.names() == ["service_health"]
    assert pack_identity(pack) == "pack:service_health/0.1.0"
    assert present(registry.observe("service_health", obs(error_rate=0.5))) == {"error_burst"}


def test_the_thresholds_are_declared_parameters_and_the_detectors_use_exactly_those_values():
    declared = {p.name: p.value for p in PARAMETERS}
    assert len(declared) == 8
    for tier, row in SERVICE_NORMS.items():
        for column, value in row.items():
            assert declared[f"{tier}_{column}"] == value
    assert ServiceHealthPack().parameters() == PARAMETERS


def test_every_parameter_is_bounded_and_says_plainly_that_nobody_approved_it():
    for p in PARAMETERS:
        assert p.minimum <= p.value <= p.maximum
        assert p.approved_by.lower().startswith("unapproved"), p.approved_by
        assert "synthetic" in p.justification.lower()


CLINICAL = re.compile(r"patient|vital|pediatric|paediatric|sepsis|tachy|fever|oxygen|heart|clinical|age_months|neonat|infant",
                      re.IGNORECASE)


def test_the_pack_names_nothing_clinical():
    offenders = []
    for path in sorted((ROOT / "alpha" / "packs" / "service_health").glob("*.py")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if CLINICAL.search(line):
                offenders.append(f"{path.name}:{number}: {line.strip()}")
    assert not offenders, offenders


def test_the_package_list_includes_the_pack():
    assert '"alpha.packs.service_health"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
