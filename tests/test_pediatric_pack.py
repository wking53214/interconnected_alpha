"""The pediatric-vitals pack: today's detectors, moved under alpha.packs.pediatric_vitals and declared as a domain pack.

The golden check is the point of the move: a digest of every detector output (names, presence, confidence, reasons, the key
fingerprint) over a grid of 20,160 readings, captured from the code BEFORE it moved (tests/golden_pediatric_keys.json), must be
reproduced exactly by the code after it moved.
"""
import importlib.util
import json
import re
from pathlib import Path

import pytest

import alpha
from alpha.cns_connector import keyset_content
from alpha.core import PackRegistry, pack_identity, pack_problems
from alpha.packs.pediatric_vitals import (
    ALL_DETECTORS,
    PEDIATRIC_NORMS,
    PediatricVitalsPack,
    VitalsObservation,
    observe,
)
from golden_grid import run

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = json.loads((ROOT / "tests" / "golden_pediatric_keys.json").read_text(encoding="utf-8"))


# ---- nothing changed in what the detectors say -------------------------------------------------------------------

def test_every_detector_output_over_the_grid_is_exactly_what_it_was_before_the_move():
    got = run(observe, VitalsObservation, keyset_content)
    assert got["count"] == GOLDEN["count"] == 20160
    assert got["sha256"] == GOLDEN["sha256"]
    assert got["sample"] == GOLDEN["sample"]


def test_the_pack_observes_the_same_keys_through_the_registry():
    registry = PackRegistry()
    registry.register(PediatricVitalsPack())
    v = VitalsObservation(heart_rate=200, oxygen_saturation=85.0, respiratory_rate=50, temperature=39.6, age_months=10)
    assert keyset_content(registry.observe("pediatric_vitals", v)) == keyset_content(observe(v))


# ---- it is a valid domain pack ----------------------------------------------------------------------------------

def test_the_pack_keeps_the_contract_and_registers():
    pack = PediatricVitalsPack()
    assert pack_problems(pack) == []
    registry = PackRegistry()
    registry.register(pack)
    assert registry.names() == ["pediatric_vitals"]
    assert pack_identity(pack) == f"pack:pediatric_vitals/{pack.VERSION}"


def test_the_pack_declares_exactly_the_keys_its_detectors_emit():
    emitted = []
    v = VitalsObservation(heart_rate=100, oxygen_saturation=99.0, respiratory_rate=20, temperature=37.0, age_months=24)
    for detector in ALL_DETECTORS:
        emitted.append(detector(v).name)
    assert tuple(emitted) == PediatricVitalsPack.KEYS
    assert len(set(PediatricVitalsPack.KEYS)) == 10


def test_the_age_group_table_is_declared_as_parameters_with_bounds():
    parameters = PediatricVitalsPack().parameters()
    assert len(parameters) == 25
    by_name = {p.name: p for p in parameters}
    for group, row in PEDIATRIC_NORMS.items():
        for key, value in row.items():
            parameter = by_name[f"{group}_{key}"]
            assert parameter.value == value
            assert parameter.minimum <= value <= parameter.maximum


def test_the_declaration_says_plainly_that_nobody_approved_the_thresholds():
    for parameter in PediatricVitalsPack().parameters():
        assert parameter.approved_by.lower().startswith("unapproved"), parameter.approved_by
        assert "not independently clinically validated" in parameter.justification


# ---- the old top-level names are gone (a clean break), and the top level names no domain -------------------------------

@pytest.mark.parametrize("name", ["VitalsObservation", "PEDIATRIC_NORMS", "get_age_group", "ALL_DETECTORS", "detect_all", "observe"])
def test_alpha_no_longer_exports_the_pediatric_names(name):
    assert not hasattr(alpha, name)


@pytest.mark.parametrize("module", ["alpha.vitals", "alpha.thresholds", "alpha.detectors", "alpha.registry"])
def test_the_old_module_paths_are_gone(module):
    assert importlib.util.find_spec(module) is None


CLINICAL = re.compile(r"patient|vital|pediatric|paediatric|sepsis|tachy|fever|oxygen|heart|clinical|age_months|neonat|infant",
                      re.IGNORECASE)


def test_nothing_in_alpha_outside_its_packs_names_a_domain():
    offenders = []
    for path in sorted((ROOT / "alpha").rglob("*.py")):
        if "packs" in path.relative_to(ROOT / "alpha").parts:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if CLINICAL.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
    assert not offenders, offenders


def test_the_package_list_includes_the_pack_directories():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"alpha.packs"' in text and '"alpha.packs.pediatric_vitals"' in text
