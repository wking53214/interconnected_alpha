"""The domain-pack contract.

A pack declares who it is (``NAME``, ``VERSION``, ``DOMAIN``), the Key names it can emit (``KEYS``), and its parameters as
data. A parameter is named, typed, bounded and documented, and carries who approved it, when, and why. There are no defaults:
a value a pack never declared is a value nobody can trace. Validation is total (every violation is listed, not just the first)
and runs on the load path, so ``PackRegistry.register`` never admits an invalid pack.

The registry also holds a pack to what it declared when it observes: the result must be exactly a ``zeta.KeySet``, every Key in it
must be one the pack declared in ``KEYS``, and every declared Key must be there (present or not).

What this does not do: it does not judge, decide or authorise (alpha detects named Keys and never says PASS or BREACH), it does
not authenticate that a pack is who it says it is, and it does not check that a parameter's approval is true. A pack's identity
(``pack_identity``) is a producer's claim, recorded like the rest of an origin record.
"""

import math
import re
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from datetime import date
from typing import Any, Dict, List, Tuple

from zeta import Key, KeySet

_NAME = re.compile(r"[a-z][a-z0-9_]*")
_NUMBER = r"(?:0|[1-9][0-9]*)"
_VERSION = re.compile(rf"{_NUMBER}\.{_NUMBER}\.{_NUMBER}")
_ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _name_ok(value: Any) -> bool:
    """An exact str of lowercase ASCII letters, digits and underscores starting with a letter. The whole string must match."""
    return type(value) is str and _NAME.fullmatch(value) is not None


class PackError(Exception):
    """A pack could not be registered or used, and why."""


class PackValidationError(PackError):
    """A pack broke its contract. ``problems`` lists every violation found."""

    def __init__(self, problems: List[str]) -> None:
        self.problems = list(problems)
        super().__init__("the pack breaks its contract: " + "; ".join(self.problems))


@dataclass(frozen=True)
class Parameter:
    """One declared parameter: its value, its bounds, and who approved it."""

    name: str
    value: float
    minimum: float
    maximum: float
    description: str
    approved_by: str
    approval_date: str  # ISO date, YYYY-MM-DD
    justification: str


class DomainPack(ABC):
    """The kernel every domain pack implements. Domain-shaped content is the subclass's, never this class's."""

    NAME: str
    VERSION: str
    DOMAIN: str
    KEYS: Tuple[str, ...]

    @abstractmethod
    def parameters(self) -> Tuple[Parameter, ...]:
        """The pack's declared parameters. Read once at registration; the registry keeps that snapshot."""

    @abstractmethod
    def observe(self, raw: Any) -> KeySet:
        """Detect this pack's Keys in one raw observation of its own type."""

    def parameter_problems(self, parameters: Tuple[Parameter, ...]) -> List[str]:
        """Relations between this pack's parameters that bounds alone cannot state (for example one limit not above another).

        Called by the registry on the validated copies, only when every parameter is individually valid. Return a message per
        violation; the default states none. A check that raises is reported as a problem, not a crash.
        """
        return []

    def identity(self) -> str:
        return pack_identity(self)


def pack_identity(pack: Any) -> str:
    """``pack:<name>/<version>``, the string a producer records with what it observed."""
    return f"pack:{pack.NAME}/{pack.VERSION}"


def _exact_str(value: Any) -> bool:
    return type(value) is str


def _finite(number: Any) -> bool:
    """``math.isfinite`` that says False, not OverflowError, for an integer too large for a float."""
    try:
        return math.isfinite(number)
    except OverflowError:
        return False


def _parameter_problems(index: int, parameter: Any) -> List[str]:
    if type(parameter) is not Parameter:
        return [f"parameters()[{index}] is not exactly a Parameter: {type(parameter).__name__}"]
    label = parameter.name if _exact_str(parameter.name) else f"parameters()[{index}]"
    out: List[str] = []
    if not _name_ok(parameter.name):
        out.append(f"{label}: name must be an exact str of lowercase letters, digits and underscores starting with a letter")
    for field in ("description", "approved_by", "justification"):
        value = getattr(parameter, field)
        if not _exact_str(value) or not value.strip():
            out.append(f"{label}: {field} must be a non-empty exact str")
    if not _exact_str(parameter.approval_date):
        out.append(f"{label}: approval_date must be an exact str in the form YYYY-MM-DD")
    else:
        try:
            if not _ISO_DATE.fullmatch(parameter.approval_date):
                raise ValueError
            date.fromisoformat(parameter.approval_date)
        except ValueError:
            out.append(f"{label}: approval_date must be a real date in the form YYYY-MM-DD, got {parameter.approval_date!r}")
    numbers = {}
    for field in ("value", "minimum", "maximum"):
        number = getattr(parameter, field)
        if type(number) not in (int, float):
            out.append(f"{label}: {field} must be an exact int or float (a bool or another type is refused), got {type(number).__name__}")
        elif not _finite(number):
            out.append(f"{label}: {field} must be finite, got {number!r}")
        else:
            numbers[field] = number
    if len(numbers) == 3:
        if numbers["minimum"] > numbers["maximum"]:
            out.append(f"{label}: minimum {numbers['minimum']!r} is above maximum {numbers['maximum']!r}")
        elif not numbers["minimum"] <= numbers["value"] <= numbers["maximum"]:
            out.append(f"{label}: value {numbers['value']!r} is outside its bounds [{numbers['minimum']!r}, {numbers['maximum']!r}]")
    return out


def _read_parameters(pack: Any) -> Tuple[Any, List[str]]:
    try:
        declared = pack.parameters()
    except Exception as exc:  # a pack that cannot state its parameters does not load
        return None, [f"parameters() raised {type(exc).__name__}: {exc}"]
    if type(declared) is not tuple:
        return None, [f"parameters() must return a tuple of Parameter; got {type(declared).__name__}"]
    return declared, []


def _read_identity(pack: Any) -> Dict[str, Any]:
    """Read NAME, VERSION, DOMAIN and KEYS once. What is validated and kept is exactly this read, never a second one."""
    return {field: getattr(pack, field, None) for field in ("NAME", "VERSION", "DOMAIN", "KEYS")}


def _problems_with(pack: Any, declared: Any, read_problems: List[str], identity: Dict[str, Any]) -> List[str]:
    if not isinstance(pack, DomainPack):
        return [f"not a DomainPack: {type(pack).__name__}"]
    out: List[str] = []
    name, version, domain, keys = identity["NAME"], identity["VERSION"], identity["DOMAIN"], identity["KEYS"]
    if not _name_ok(name):
        out.append("NAME must be an exact str of lowercase letters, digits and underscores starting with a letter")
    if not (_exact_str(version) and _VERSION.fullmatch(version)):
        out.append("VERSION must be an exact str of the form MAJOR.MINOR.PATCH")
    if not _exact_str(domain) or not domain.strip():
        out.append("DOMAIN must be a non-empty exact str")
    if type(keys) is not tuple or not keys:
        out.append("KEYS must be a non-empty tuple of Key names")
    else:
        bad = [k for k in keys if not _name_ok(k)]
        if bad:
            out.append(f"KEYS must hold only exact str names of lowercase ASCII letters, digits and underscores starting with a letter; got {bad!r}")
        names = [k for k in keys if _name_ok(k)]
        repeated = sorted({k for k in names if names.count(k) > 1})
        if repeated:
            out.append(f"KEYS names {repeated!r} appear twice")
    out.extend(read_problems)
    if declared is not None:
        seen: Dict[str, int] = {}
        for index, parameter in enumerate(declared):
            out.extend(_parameter_problems(index, parameter))
            if type(parameter) is Parameter and _exact_str(parameter.name):
                seen[parameter.name] = seen.get(parameter.name, 0) + 1
        for parameter_name, count in sorted(seen.items()):
            if count > 1:
                out.append(f"{parameter_name}: declared {count} times; a parameter is named once ({parameter_name} appears twice)")
        if not out and all(type(p) is Parameter for p in declared):
            try:
                out.extend(str(m) for m in pack.parameter_problems(declared))
            except Exception as exc:  # a relation check that cannot run is a problem with the pack, not a crash here
                out.append(f"parameter_problems raised {type(exc).__name__}: {exc}")
    return out


def pack_problems(pack: Any) -> List[str]:
    """Every way ``pack`` breaks the contract, in one list (empty when it keeps it)."""
    if not isinstance(pack, DomainPack):
        return _problems_with(pack, None, [], {})
    declared, read_problems = _read_parameters(pack)
    return _problems_with(pack, declared, read_problems, _read_identity(pack))


def validate_pack(pack: Any) -> None:
    """Raise ``PackValidationError`` listing every violation, or return."""
    problems = pack_problems(pack)
    if problems:
        raise PackValidationError(problems)


@dataclass(frozen=True)
class _Entry:
    """What the registry validated and keeps: its own copies, never the pack's objects read again."""

    pack: DomainPack
    name: str
    version: str
    keys: Tuple[str, ...]
    parameters: Tuple[Parameter, ...]


class PackRegistry:
    """Loads packs, fail-loud. A name is registered once; nothing is defaulted.

    At registration the registry reads the pack's NAME, VERSION, DOMAIN, KEYS and parameters once, validates exactly what it read, and
    keeps those values and its own copies of the parameters. Later calls use the kept values, so a pack whose attributes change after
    registration cannot change what was admitted, its recorded identity or the Keys it is allowed to emit.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: Dict[str, _Entry] = {}

    def register(self, pack: Any) -> None:
        if not isinstance(pack, DomainPack):
            raise PackValidationError(pack_problems(pack))
        identity = _read_identity(pack)
        declared, read_problems = _read_parameters(pack)  # read once: this snapshot is validated and kept
        if declared is not None and all(type(p) is Parameter for p in declared):
            declared = tuple(replace(p) for p in declared)  # the registry's own copies: later edits to the pack's do not reach them
        problems = _problems_with(pack, declared, read_problems, identity)
        if problems:
            raise PackValidationError(problems)
        entry = _Entry(pack=pack, name=identity["NAME"], version=identity["VERSION"], keys=identity["KEYS"], parameters=declared)
        with self._lock:
            if entry.name in self._entries:
                raise PackError(f"a pack named {entry.name!r} is already registered (version {self._entries[entry.name].version})")
            self._entries[entry.name] = entry

    def _entry(self, name: str) -> _Entry:
        with self._lock:
            if name not in self._entries:
                raise PackError(f"no pack named {name!r} is registered")
            return self._entries[name]

    def get(self, name: str) -> DomainPack:
        return self._entry(name).pack

    def identity(self, name: str) -> str:
        """``pack:<name>/<version>`` from the values read and validated at registration, not from the pack as it is now."""
        entry = self._entry(name)
        return f"pack:{entry.name}/{entry.version}"

    def parameters(self, name: str) -> Tuple[Parameter, ...]:
        """The parameters as they were when the pack registered."""
        return self._entry(name).parameters

    def names(self) -> List[str]:
        with self._lock:
            return sorted(self._entries)

    def observe(self, name: str, raw: Any) -> KeySet:
        """Run the named pack and hold it to what it declared. What is returned is a ``KeySet`` the registry built itself.

        The pack must return exactly a ``zeta.KeySet`` of exact ``Key`` objects with exact ``str`` names, every one in the ``KEYS`` read at
        registration. The Keys are read through the classes' own accessors (not the instance's, which a pack could shadow) and copied
        into a new ``KeySet``, so nothing the pack attached to its own objects reaches the caller.
        """
        entry = self._entry(name)
        returned = entry.pack.observe(raw)
        if type(returned) is not KeySet:
            raise PackError(f"pack {name!r} returned {type(returned).__name__}, not exactly a zeta KeySet")
        rebuilt = []
        for key in KeySet.all_keys(returned):
            if type(key) is not Key or type(key.name) is not str:
                raise PackError(f"pack {name!r} returned a Key that is not exactly a zeta Key with an exact str name")
            rebuilt.append(Key(name=key.name, present=key.present, confidence=key.confidence, reason=key.reason))
        undeclared = sorted({key.name for key in rebuilt} - set(entry.keys))
        if undeclared:
            raise PackError(f"pack {name!r} emitted Keys it did not declare in KEYS: {undeclared}")
        omitted = sorted(set(entry.keys) - {key.name for key in rebuilt})
        if omitted:
            raise PackError(f"pack {name!r} did not emit Keys it declared in KEYS: {omitted} (every declared Key is returned on every observation, present or not)")
        return KeySet(rebuilt, min_confidence=returned.min_confidence)
