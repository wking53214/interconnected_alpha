"""Two unrelated domains, one contract: everything alpha promises about a pack holds for the pediatric pack and the service-health pack alike."""
from datetime import datetime

import pytest
from zeta import Combination, LockEvaluator, LockRegistry, LockSpec

from alpha.cns_connector import CONTEXT_SCHEMA, keyset_content
from alpha.core import PackRegistry, pack_identity, pack_problems
from alpha.packs.pediatric_vitals import PediatricVitalsPack, VitalsObservation
from alpha.packs.service_health import ServiceHealthPack, ServiceObservation

PEDIATRIC_SAMPLES = [
    VitalsObservation(heart_rate=100, oxygen_saturation=99.0, respiratory_rate=20, temperature=37.0, age_months=24),
    VitalsObservation(heart_rate=200, oxygen_saturation=85.0, respiratory_rate=50, temperature=39.6, age_months=10),
    VitalsObservation(heart_rate=60, oxygen_saturation=91.0, respiratory_rate=12, temperature=34.0, age_months=1),
]
SERVICE_SAMPLES = [
    ServiceObservation(latency_p95_ms=120.0, error_rate=0.001, queue_depth=5, tier="interactive"),
    ServiceObservation(latency_p95_ms=1500.0, error_rate=0.2, queue_depth=900, tier="interactive"),
    ServiceObservation(latency_p95_ms=6000.0, error_rate=0.0, queue_depth=0, tier="batch"),
]
CASES = [(PediatricVitalsPack, PEDIATRIC_SAMPLES), (ServiceHealthPack, SERVICE_SAMPLES)]
IDS = ["pediatric_vitals", "service_health"]
NOW = datetime(2026, 11, 13, 12, 0, 0)


@pytest.fixture(params=CASES, ids=IDS)
def case(request):
    pack_class, samples = request.param
    return pack_class(), samples


def test_each_pack_keeps_the_contract(case):
    pack, _ = case
    assert pack_problems(pack) == []


def test_both_packs_live_in_one_registry_without_interfering():
    registry = PackRegistry()
    registry.register(PediatricVitalsPack())
    registry.register(ServiceHealthPack())
    assert registry.names() == ["pediatric_vitals", "service_health"]
    assert registry.observe("pediatric_vitals", PEDIATRIC_SAMPLES[1]).names_present()
    assert registry.observe("service_health", SERVICE_SAMPLES[1]).names_present()


def test_the_registry_holds_each_pack_to_the_keys_it_declared(case):
    pack, samples = case
    registry = PackRegistry()
    registry.register(pack)
    for raw in samples:
        names = {k.name for k in registry.observe(pack.NAME, raw).all_keys()}
        assert names <= set(pack.KEYS)


def test_observing_twice_gives_the_same_keys(case):
    pack, samples = case
    for raw in samples:
        assert keyset_content(pack.observe(raw)) == keyset_content(pack.observe(raw))


def test_the_pack_identity_is_distinct_and_names_the_version(case):
    pack, _ = case
    assert pack_identity(pack) == f"pack:{pack.NAME}/{pack.VERSION}"


def test_a_pack_records_itself_in_the_existing_origin_field_and_nothing_new_is_needed(case):
    """No new hashed field: the identity goes in origin.transformation, which is already bound into the digest."""
    pack, samples = case
    ctx = {"schema": CONTEXT_SCHEMA, "entity_id": "entity-1", "event_id": "event-1", "run_id": "run-1"}

    def origin(identity):
        return {"source": "test", "producer": "test", "observed_at": "2026-11-13T12:00:00", "collection_context": "test",
                "transformation": identity}

    keys = pack.observe(samples[0])
    content = keyset_content(keys, context=ctx, origin=origin(pack_identity(pack)))
    assert content["origin"]["transformation"] == pack_identity(pack)
    other = keyset_content(keys, context=ctx, origin=origin("pack:someone_else/9.9.9"))
    assert other != content  # the identity is part of what is bound


def test_each_packs_keys_feed_zeta_locks(case):
    pack, samples = case
    registry = LockRegistry([LockSpec(lock_id="any_lock", required_keys=pack.KEYS, combination=Combination.OR,
                                      dwell_threshold=1, force=True, lock_seconds=3600)])
    evaluator = LockEvaluator(registry)
    opened = [evaluator.evaluate_all("entity-1", pack.observe(raw), NOW)["any_lock"].open for raw in samples]
    assert any(opened) and not all(opened)  # the samples include a quiet one and an alarming one
