"""The service-health domain pack: a second domain under the same ``alpha.core.DomainPack`` contract."""

from typing import Tuple

from zeta import KeySet

from ...core import DomainPack, Parameter
from .observation import ServiceObservation
from .registry import observe
from .thresholds import PARAMETERS, TIER_NAMES, norms_from


class ServiceHealthPack(DomainPack):
    NAME = "service_health"
    VERSION = "0.1.0"
    DOMAIN = "service_operations"
    KEYS: Tuple[str, ...] = ("latency_high", "latency_critical", "error_burst", "queue_backlog", "degraded_service")

    def parameters(self) -> Tuple[Parameter, ...]:
        return PARAMETERS

    def parameter_problems(self, parameters):
        by_name = {p.name: p.value for p in parameters}
        return [f"{tier}_latency_critical ({by_name[f'{tier}_latency_critical']}) is below {tier}_latency_high "
                f"({by_name[f'{tier}_latency_high']}); critical latency is also high latency"
                for tier in TIER_NAMES if by_name[f"{tier}_latency_critical"] < by_name[f"{tier}_latency_high"]]

    def _norms(self):
        """The threshold table, built once from this pack's parameters: the values the registry validated are the values used."""
        if not hasattr(self, "_norms_cache"):
            self._norms_cache = norms_from(self.parameters())
        return self._norms_cache

    def observe(self, raw: ServiceObservation) -> KeySet:
        if type(raw) is not ServiceObservation:
            raise TypeError(f"ServiceHealthPack.observe needs exactly a ServiceObservation, got {type(raw).__name__}")
        # a fresh object: its own validation runs again, so an observation edited after construction is refused here
        raw = ServiceObservation(raw.latency_p95_ms, raw.error_rate, raw.queue_depth, raw.tier)
        return observe(raw, self._norms())
