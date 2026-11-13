"""The service-health domain pack: a second domain under the same ``alpha.core.DomainPack`` contract."""

from typing import Tuple

from zeta import KeySet

from ...core import DomainPack, Parameter
from .observation import ServiceObservation
from .registry import observe
from .thresholds import PARAMETERS


class ServiceHealthPack(DomainPack):
    NAME = "service_health"
    VERSION = "0.1.0"
    DOMAIN = "service_operations"
    KEYS: Tuple[str, ...] = ("latency_high", "latency_critical", "error_burst", "queue_backlog", "degraded_service")

    def parameters(self) -> Tuple[Parameter, ...]:
        return PARAMETERS

    def observe(self, raw: ServiceObservation) -> KeySet:
        return observe(raw)
