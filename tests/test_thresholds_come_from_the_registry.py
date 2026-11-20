"""The thresholds the detectors use are the copies the registry validated, not a later call to parameters().

EXECUTED 2026-11-17 (README): a pack whose parameters() gave valid values at registration and different valid values afterwards
registered cleanly and then observed with the later values. The registry now hands its validated copies back to the pack.
"""
import dataclasses

from alpha.core import PackRegistry
from alpha.packs.pediatric_vitals import PediatricVitalsPack, VitalsObservation
from alpha.packs.service_health import ServiceHealthPack, ServiceObservation


class DriftingService(ServiceHealthPack):
    """Declares the real values on its first call and a very high latency limit on every later call."""

    calls = 0

    def parameters(self):
        type(self).calls += 1
        declared = super().parameters()
        if type(self).calls == 1:
            return declared
        return tuple(dataclasses.replace(p, value=3_000_000.0) if p.name == "interactive_latency_high" else p for p in declared)


class DriftingPediatric(PediatricVitalsPack):
    calls = 0

    def parameters(self):
        type(self).calls += 1
        declared = super().parameters()
        if type(self).calls == 1:
            return declared
        return tuple(dataclasses.replace(p, value=p.minimum) if p.name == "generic_hr_high" else p for p in declared)


def test_service_pack_uses_the_values_the_registry_validated():
    DriftingService.calls = 0
    registry = PackRegistry()
    registry.register(DriftingService())
    keys = registry.observe(DriftingService.NAME, ServiceObservation(2000.0, 0.001, 5, "interactive"))
    assert {k.name: k.present for k in keys.all_keys()}["latency_high"] is True


def test_pediatric_pack_uses_the_values_the_registry_validated():
    DriftingPediatric.calls = 0
    registry = PackRegistry()
    registry.register(DriftingPediatric())
    keys = registry.observe(DriftingPediatric.NAME, VitalsObservation(100, 98.0, 20, 36.8, None))
    assert {k.name: k.present for k in keys.all_keys()}["tachycardia"] is False


def test_a_pack_used_directly_still_reads_its_own_parameters():
    pack = ServiceHealthPack()
    keys = pack.observe(ServiceObservation(2000.0, 0.001, 5, "interactive"))
    assert {k.name: k.present for k in keys.all_keys()}["latency_high"] is True
