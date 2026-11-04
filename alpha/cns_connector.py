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
from collections.abc import Mapping
from types import ModuleType
from typing import Any, Dict, Optional

from zeta import Key, KeySet

__all__ = [
    "CONTEXT_SCHEMA",
    "CnsNotInstalled",
    "KEYSET_SUBJECT",
    "binds",
    "cns_available",
    "keyset_content",
    "keyset_digest",
]

INSTALL_HINT = "pip install 'alpha[cns] @ git+https://github.com/wking53214/interconnected_alpha'"

KEYSET_SUBJECT = "alpha.keyset"

# One pipeline run, named the same way by every stage's connector (CNS publishes the contract in
# cns_composition.pipeline_context and holds the four copies to it). A plain mapping, so alpha imports nothing.
CONTEXT_SCHEMA = "spine-context/1"
_CONTEXT_FIELDS = ("schema", "entity_id", "event_id", "run_id")


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


def _context(context: Any) -> Dict[str, str]:
    """A validated copy of a pipeline context: exactly the four fields, all non-empty strings, a known schema."""
    if not isinstance(context, Mapping):
        raise TypeError(f"a pipeline context must be a mapping; got {type(context).__name__}")
    if set(context) != set(_CONTEXT_FIELDS):
        raise ValueError(f"a pipeline context has exactly the fields {list(_CONTEXT_FIELDS)}; got {sorted(map(str, context))}")
    for name in _CONTEXT_FIELDS:
        if not isinstance(context[name], str):
            raise TypeError(f"context field {name} must be a str; got {type(context[name]).__name__}")
        if not context[name]:
            raise ValueError(f"context field {name} must be non-empty")
    if context["schema"] != CONTEXT_SCHEMA:
        raise ValueError(f"unsupported context schema {context['schema']!r}; this connector speaks {CONTEXT_SCHEMA!r}")
    return {name: context[name] for name in _CONTEXT_FIELDS}


def keyset_content(keyset: KeySet, *, context: Optional[Mapping] = None) -> Dict[str, Any]:
    """The deterministic content a verdict on ``keyset`` is bound to.

    ``context`` (schema, entity_id, event_id, run_id) binds the keys to the observation they came from. With it the
    content gains ``context`` and ``present_names``, the sorted names zeta's KeySet rule treats as present (present
    and at or above ``min_confidence``), so a reader never has to re-derive that rule. Without it the content is
    exactly what it always was.
    """
    if not isinstance(keyset, KeySet):
        raise TypeError(f"expected a zeta KeySet; got {type(keyset).__name__}")
    keys = sorted((_key_content(k) for k in keyset.all_keys()), key=lambda c: c["name"])
    content: Dict[str, Any] = {"min_confidence": float(keyset.min_confidence), "keys": keys}
    if context is not None:
        content["context"] = _context(context)
        content["present_names"] = sorted(keyset.names_present())
    return content


def keyset_digest(keyset: KeySet, *, context: Optional[Mapping] = None) -> str:
    """The digest a verdict bound to ``keyset`` carries."""
    return _cns_gate().subject_digest(keyset_content(keyset, context=context))


def binds(result: Any, keyset: KeySet, *, subject: str = KEYSET_SUBJECT, context: Optional[Mapping] = None) -> bool:
    """Whether the ``cns.gate.GateResult`` ``result`` was issued against exactly ``keyset``.

    An unbound or hand-built result is ``False``. This checks what a verdict
    was about; it says nothing about what the verdict was.
    """
    digest = keyset_digest(keyset, context=context)
    return bool(result.binds(subject, digest))
