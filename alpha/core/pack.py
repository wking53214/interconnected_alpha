"""The domain-pack contract.

A pack declares who it is (``NAME``, ``VERSION``, ``DOMAIN``), the Key names it can emit (``KEYS``), and its parameters as
data. A parameter is named, typed, bounded and documented, and carries who approved it, when, and why. There are no defaults:
a value a pack never declared is a value nobody can trace. Validation is total (every violation is listed, not just the first)
and runs on the load path, so ``PackRegistry.register`` never admits an invalid pack.

The registry also holds a pack to what it declared when it observes: the result must be exactly a ``zeta.KeySet`` and every
Key in it must be one the pack declared in ``KEYS``.

What this does not do: it does not judge, decide or authorise (alpha detects named Keys and never says PASS or BREACH), it does
not authenticate that a pack is who it says it is, and it does not check that a parameter's approval is true. A pack's identity
(``pack_identity``) is a producer's claim, recorded like the rest of an origin record.
"""

import math
import re
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Tuple

from zeta import KeySet

_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_VERSION = re.compile(r"^\d+\.\d+\.\d+$")


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

    def identity(self) -> str:
        return pack_identity(self)


def pack_identity(pack: Any) -> str:
    """``pack:<name>/<version>``, the string a producer records with what it observed."""
    return f"pack:{pack.NAME}/{pack.VERSION}"


def _exact_str(value: Any) -> bool:
    return type(value) is str


def _parameter_problems(index: int, parameter: Any) -> List[str]:
    if type(parameter) is not Parameter:
        return [f"parameters()[{index}] is not exactly a Parameter: {type(parameter).__name__}"]
    label = parameter.name if _exact_str(parameter.name) else f"parameters()[{index}]"
    out: List[str] = []
    if not _exact_str(parameter.name) or not _NAME.match(parameter.name):
        out.append(f"{label}: name must be an exact str of lowercase letters, digits and underscores starting with a letter")
    for field in ("description", "approved_by", "justification"):
        value = getattr(parameter, field)
        if not _exact_str(value) or not value.strip():
            out.append(f"{label}: {field} must be a non-empty exact str")
    if not _exact_str(parameter.approval_date):
        out.append(f"{label}: approval_date must be an exact str in the form YYYY-MM-DD")
    else:
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", parameter.approval_date):
                raise ValueError
            date.fromisoformat(parameter.approval_date)
        except ValueError:
            out.append(f"{label}: approval_date must be a real date in the form YYYY-MM-DD, got {parameter.approval_date!r}")
    numbers = {}
    for field in ("value", "minimum", "maximum"):
        number = getattr(parameter, field)
        if type(number) not in (int, float):
            out.append(f"{label}: {field} must be an exact int or float (a bool or another type is refused), got {type(number).__name__}")
        elif not math.isfinite(number):
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


def _problems_with(pack: Any, declared: Any, read_problems: List[str]) -> List[str]:
    if not isinstance(pack, DomainPack):
        return [f"not a DomainPack: {type(pack).__name__}"]
    out: List[str] = []
    name: Any = getattr(pack, "NAME", None)
    version: Any = getattr(pack, "VERSION", None)
    domain: Any = getattr(pack, "DOMAIN", None)
    keys: Any = getattr(pack, "KEYS", None)
    if not _exact_str(name) or not _NAME.match(name):
        out.append("NAME must be an exact str of lowercase letters, digits and underscores starting with a letter")
    if not _exact_str(version) or not _VERSION.match(version):
        out.append("VERSION must be an exact str of the form MAJOR.MINOR.PATCH")
    if not _exact_str(domain) or not domain.strip():
        out.append("DOMAIN must be a non-empty exact str")
    if type(keys) is not tuple or not keys:
        out.append("KEYS must be a non-empty tuple of Key names")
    else:
        bad = [k for k in keys if not _exact_str(k) or not k.strip()]
        if bad:
            out.append(f"KEYS must hold only non-empty exact str names; got {bad!r}")
        names = [k for k in keys if _exact_str(k)]
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
    return out


def pack_problems(pack: Any) -> List[str]:
    """Every way ``pack`` breaks the contract, in one list (empty when it keeps it)."""
    if not isinstance(pack, DomainPack):
        return _problems_with(pack, None, [])
    declared, read_problems = _read_parameters(pack)
    return _problems_with(pack, declared, read_problems)


def validate_pack(pack: Any) -> None:
    """Raise ``PackValidationError`` listing every violation, or return."""
    problems = pack_problems(pack)
    if problems:
        raise PackValidationError(problems)


class PackRegistry:
    """Loads packs, fail-loud. A name is registered once; nothing is defaulted."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._packs: Dict[str, DomainPack] = {}
        self._parameters: Dict[str, Tuple[Parameter, ...]] = {}

    def register(self, pack: Any) -> None:
        if not isinstance(pack, DomainPack):
            raise PackValidationError(pack_problems(pack))
        declared, read_problems = _read_parameters(pack)  # read once: the same snapshot is validated and kept
        problems = _problems_with(pack, declared, read_problems)
        if problems:
            raise PackValidationError(problems)
        with self._lock:
            if pack.NAME in self._packs:
                raise PackError(f"a pack named {pack.NAME!r} is already registered (version {self._packs[pack.NAME].VERSION})")
            self._packs[pack.NAME] = pack
            self._parameters[pack.NAME] = declared

    def get(self, name: str) -> DomainPack:
        with self._lock:
            if name not in self._packs:
                raise PackError(f"no pack named {name!r} is registered")
            return self._packs[name]

    def parameters(self, name: str) -> Tuple[Parameter, ...]:
        """The parameters as they were when the pack registered."""
        with self._lock:
            if name not in self._parameters:
                raise PackError(f"no pack named {name!r} is registered")
            return self._parameters[name]

    def names(self) -> List[str]:
        with self._lock:
            return sorted(self._packs)

    def observe(self, name: str, raw: Any) -> KeySet:
        """Run the named pack and hold it to what it declared: exactly a ``KeySet`` whose Keys are all in ``KEYS``."""
        pack = self.get(name)
        keys = pack.observe(raw)
        if type(keys) is not KeySet:
            raise PackError(f"pack {name!r} returned {type(keys).__name__}, not exactly a zeta KeySet")
        undeclared = sorted({key.name for key in keys.all_keys()} - set(pack.KEYS))
        if undeclared:
            raise PackError(f"pack {name!r} emitted Keys it did not declare in KEYS: {undeclared}")
        return keys
