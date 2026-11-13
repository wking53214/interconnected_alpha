"""alpha.core: the domain-blind contract a domain pack implements, and the registry that admits one.

A domain pack turns raw observations from one domain into a ``zeta.KeySet``. Everything domain-shaped (the raw type, the
detectors, the thresholds) lives in a pack; this core names no domain. See ``alpha.core.pack``.
"""

from .pack import (
    DomainPack,
    PackError,
    PackRegistry,
    PackValidationError,
    Parameter,
    pack_identity,
    pack_problems,
    validate_pack,
)

__all__ = [
    "DomainPack",
    "PackError",
    "PackRegistry",
    "PackValidationError",
    "Parameter",
    "pack_identity",
    "pack_problems",
    "validate_pack",
]
