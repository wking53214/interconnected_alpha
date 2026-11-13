"""alpha: the observation layer. Domain packs turn raw observations into named Keys for interconnected_zeta's Locks.

``alpha.core`` is the domain-blind contract and registry; ``alpha.packs`` holds the packs (one subpackage per domain);
``alpha.cns_connector`` binds a ``KeySet`` for CNS. This package names no domain: every detector lives in a pack
under ``alpha.packs``.
"""

from .core import (
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

__version__ = "0.2.0"
