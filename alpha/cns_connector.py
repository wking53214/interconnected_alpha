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

The raw observations are not bound (the keys do not record them beyond their reasons),
and alpha identifies no subject, so identical keys for two subjects bind
alike.

Install with the extra:
``pip install 'alpha[cns] @ git+https://github.com/wking53214/interconnected_alpha'``.
"""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from datetime import datetime
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
# cns_composition.spine_trace.context_problems, which the integration runner holds the four copies to). A plain
# mapping, so alpha imports nothing.
CONTEXT_SCHEMA = "spine-context/1"
_CONTEXT_FIELDS = ("schema", "entity_id", "event_id", "run_id")
_ORIGIN_FIELDS = ("source", "producer", "observed_at", "collection_context", "transformation")


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
    """A validated snapshot of a pipeline context: exactly the four fields, all non-empty exact str, a known schema."""
    if not isinstance(context, Mapping):
        raise TypeError(f"a pipeline context must be a mapping; got {type(context).__name__}")
    snapshot = dict(context)  # read once; everything below validates and returns this copy, never the live mapping
    if set(snapshot) != set(_CONTEXT_FIELDS):
        raise ValueError(f"a pipeline context has exactly the fields {list(_CONTEXT_FIELDS)}; got {sorted(map(str, snapshot))}")
    for name in _CONTEXT_FIELDS:
        if type(snapshot[name]) is not str:
            raise TypeError(f"context field {name} must be a str (exact type, not a subclass); got {type(snapshot[name]).__name__}")
        if not snapshot[name]:
            raise ValueError(f"context field {name} must be non-empty")
    if snapshot["schema"] != CONTEXT_SCHEMA:
        raise ValueError(f"unsupported context schema {snapshot['schema']!r}; this connector speaks {CONTEXT_SCHEMA!r}")
    return snapshot


def _origin(origin: Any) -> Dict[str, str]:
    """A validated snapshot of an origin record: exactly the five fields, each a non-empty exact str.

    These are the producer's own assertions. Nothing here authenticates them or checks that they are true;
    ``observed_at`` is only required to parse as ISO 8601 (``datetime.fromisoformat``).
    """
    if not isinstance(origin, Mapping):
        raise TypeError(f"an origin must be a mapping; got {type(origin).__name__}")
    snapshot = dict(origin)  # read once; validate and return this copy
    if set(snapshot) != set(_ORIGIN_FIELDS):
        raise ValueError(f"an origin has exactly the fields {list(_ORIGIN_FIELDS)}; got {sorted(map(str, snapshot))}")
    for name in _ORIGIN_FIELDS:
        if type(snapshot[name]) is not str:
            raise TypeError(f"origin field {name} must be a str (exact type, not a subclass); got {type(snapshot[name]).__name__}")
        if not snapshot[name]:
            raise ValueError(f"origin field {name} must be non-empty")
    try:
        datetime.fromisoformat(snapshot["observed_at"])
    except ValueError:
        raise ValueError(f"origin field observed_at must be ISO 8601 text; got {snapshot['observed_at']!r}") from None
    return {name: snapshot[name] for name in _ORIGIN_FIELDS}


def keyset_content(keyset: KeySet, *, context: Optional[Mapping] = None, origin: Optional[Mapping] = None) -> Dict[str, Any]:
    """The deterministic content a verdict on ``keyset`` is bound to.

    ``context`` (schema, entity_id, event_id, run_id) binds the keys to the observation they came from. With it the
    content gains ``context``, ``present_names``, the sorted names zeta's KeySet rule treats as present (present
    and at or above ``min_confidence``), so a reader never has to re-derive that rule, and ``keyset_fingerprint``,
    zeta's own fingerprint of this KeySet, which a LockResult records for the KeySet it was evaluated from. Without it the content is
    exactly what it always was.

    ``origin`` (source, producer, observed_at, collection_context, transformation) records, when supplied, who
    claims to have produced the readings, from what source, when observed, in what collection context and by what
    transformation. It is added as ``origin`` only when supplied, so content without it is unchanged. These are
    the producer's own assertions bound into the digest: alpha does not authenticate them and makes no claim
    about authorization or truthfulness.
    """
    if not isinstance(keyset, KeySet):
        raise TypeError(f"expected a zeta KeySet; got {type(keyset).__name__}")
    origin_copy = None if origin is None else _origin(origin)  # validated before anything else is built
    keys = sorted((_key_content(k) for k in keyset.all_keys()), key=lambda c: c["name"])
    content: Dict[str, Any] = {"min_confidence": float(keyset.min_confidence), "keys": keys}
    if context is not None:
        fingerprint = getattr(keyset, "fingerprint", None)
        if not callable(fingerprint):
            raise ValueError(
                "this zeta's KeySet has no fingerprint(); binding keys to a run needs the zeta that records it"
            )
        content["context"] = _context(context)
        content["present_names"] = sorted(keyset.names_present())
        content["keyset_fingerprint"] = fingerprint()
    if origin_copy is not None:
        content["origin"] = origin_copy
    return content


def keyset_digest(keyset: KeySet, *, context: Optional[Mapping] = None, origin: Optional[Mapping] = None) -> str:
    """The digest a verdict bound to ``keyset`` carries."""
    return _cns_gate().subject_digest(keyset_content(keyset, context=context, origin=origin))


def binds(
    result: Any,
    keyset: KeySet,
    *,
    subject: str = KEYSET_SUBJECT,
    context: Optional[Mapping] = None,
    origin: Optional[Mapping] = None,
) -> bool:
    """Whether the ``cns.gate.GateResult`` ``result`` was issued against exactly ``keyset``.

    An unbound or hand-built result is ``False``. This checks what a verdict
    was about; it says nothing about what the verdict was.
    """
    digest = keyset_digest(keyset, context=context, origin=origin)
    return bool(result.binds(subject, digest))
