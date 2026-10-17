"""Optional connector to CNS (``cns.gate``): binding only.

alpha is independent of CNS. It has no runtime dependency on it, imports
nothing from CNS when it loads, and its whole suite passes with CNS absent.
This module is the one place that knows CNS exists, and it asks for CNS only
when a digest is computed. Without CNS those calls raise
:class:`CnsNotInstalled` with the install command; nothing else in alpha is
affected. :func:`keyset_content` is pure and needs no CNS at all.

What connecting means
---------------------
CNS's shared gate contract is ``cns.gate.GateResult``, whose ``subject`` and
``subject_digest`` record what a verdict was issued against, and whose
``binds(subject, digest)`` says whether it was issued against exactly some
content. This module makes alpha's output *bindable*: given the ``KeySet``
that ``observe`` returns, it produces the deterministic content and digest a
CNS verdict about those keys carries, and :func:`binds` checks a verdict
against the keys.

It is deliberately NOT a gate. alpha detects named Keys; it does not evaluate
Locks, policy or authorization, and it must never say PASS / RETRY / BREACH.
Binding only: no gate, no verdict mapping, no chain.

What is bound
-------------
The ``KeySet`` (subject label :data:`KEYSET_SUBJECT`): its ``min_confidence``
and, for every Key it holds, ``name``, ``present``, ``confidence`` and
``reason``. The reason text is kept because it carries the readings and
thresholds each detector compared. Keys are listed by name, so the order they
were added in cannot change the digest. ``present`` and ``confidence`` are
normalised to ``bool`` and ``float``, so ``confidence=1`` and ``1.0`` are the
same record.

The vitals are not bound (the keys do not record them beyond their reasons),
and alpha identifies no patient, so identical keys for two patients bind
alike.

Install with the extra:
``pip install 'alpha[cns] @ git+https://github.com/wking53214/interconnected_alpha'``.
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any, Dict

from zeta import Key, KeySet

__all__ = [
    "CnsNotInstalled",
    "KEYSET_SUBJECT",
    "binds",
    "cns_available",
    "keyset_content",
    "keyset_digest",
]

INSTALL_HINT = "pip install 'alpha[cns] @ git+https://github.com/wking53214/interconnected_alpha'"

KEYSET_SUBJECT = "alpha.keyset"


class CnsNotInstalled(ImportError):
    """Raised by this module's digest functions when ``cns`` cannot be imported."""


def _cns_gate() -> ModuleType:
    """Import ``cns.gate`` on demand, or say exactly what is missing."""
    try:
        return importlib.import_module("cns.gate")
    except ImportError as exc:
        raise CnsNotInstalled(
            "alpha.cns_connector needs the CNS package (cns.gate), which is not "
            f"installed. Install it with: {INSTALL_HINT}. alpha itself works "
            "without it."
        ) from exc


def cns_available() -> bool:
    """Whether the CNS gate contract can be imported in this environment."""
    try:
        _cns_gate()
    except CnsNotInstalled:
        return False
    return True


def _key_content(key: Key) -> Dict[str, Any]:
    if not isinstance(key, Key):
        raise TypeError(f"a KeySet holds Key values; got {type(key).__name__}")
    if not isinstance(key.name, str) or not isinstance(key.reason, str):
        raise TypeError("Key.name and Key.reason must be str to be bound")
    return {
        "name": key.name,
        "present": bool(key.present),
        "confidence": float(key.confidence),
        "reason": key.reason,
    }


def keyset_content(keyset: KeySet) -> Dict[str, Any]:
    """The deterministic content a verdict on ``keyset`` is bound to."""
    if not isinstance(keyset, KeySet):
        raise TypeError(f"expected a zeta KeySet; got {type(keyset).__name__}")
    keys = sorted((_key_content(k) for k in keyset.all_keys()), key=lambda c: c["name"])
    return {"min_confidence": float(keyset.min_confidence), "keys": keys}


def keyset_digest(keyset: KeySet) -> str:
    """The digest a verdict bound to ``keyset`` carries."""
    return _cns_gate().subject_digest(keyset_content(keyset))


def binds(result: Any, keyset: KeySet, *, subject: str = KEYSET_SUBJECT) -> bool:
    """Whether the ``cns.gate.GateResult`` ``result`` was issued against exactly ``keyset``.

    An unbound or hand-built result is ``False``. This checks what a verdict
    was about; it says nothing about what the verdict was.
    """
    digest = keyset_digest(keyset)
    return bool(result.binds(subject, digest))
