"""alpha is independent of CNS, and these tests hold whether or not CNS is installed.

Each runs in a fresh interpreter in which ``cns`` is blocked outright
(``sys.modules['cns'] = None`` makes any import of it fail), so the result does not
depend on what the test environment happens to contain. They never skip.
alpha depends on zeta by git URL; that is kept, and only ``cns`` is ruled out.
"""
import ast
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "alpha"
BLOCK = "import sys; sys.modules['cns'] = None; sys.modules['cns.gate'] = None\n"
# zeta is a dependency of alpha, so the fresh interpreter must find it wherever this one does.
ENV = {"PYTHONPATH": os.pathsep.join([str(ROOT)] + [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p]),
       "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONDONTWRITEBYTECODE": "1"}


def run(code: str, *, block: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", (BLOCK if block else "") + textwrap.dedent(code)],
                          capture_output=True, text=True, env=ENV, timeout=120)


def ok(done: subprocess.CompletedProcess) -> None:
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip().endswith("ok"), done.stdout


def test_the_package_and_its_connector_import_with_cns_blocked():
    ok(run("import alpha, alpha.cns_connector; print('ok')"))


def test_alpha_still_does_its_job_with_cns_blocked():
    ok(run("""
        from alpha import VitalsObservation, observe
        ks = observe(VitalsObservation(heart_rate=145, oxygen_saturation=90.0, respiratory_rate=36,
                                       temperature=39.6, age_months=48))
        assert ks.is_present("septic_shock") and ks.is_present("fever") and len(ks) == 10, ks
        print('ok')
    """))


def test_the_connector_says_what_is_missing_when_cns_is_blocked():
    ok(run("""
        from alpha import VitalsObservation, observe
        from alpha.cns_connector import CnsNotInstalled, binds, cns_available, keyset_content, keyset_digest
        assert cns_available() is False
        ks = observe(VitalsObservation(heart_rate=145, oxygen_saturation=90.0, respiratory_rate=36,
                                       temperature=39.6, age_months=48))
        assert len(keyset_content(ks)["keys"]) == 10               # content is pure and needs no cns
        for call in (lambda: keyset_digest(ks), lambda: binds(object(), ks)):
            try:
                call()
            except CnsNotInstalled as e:
                assert isinstance(e, ImportError)
                assert "pip install 'alpha[cns]" in str(e) and "alpha itself works without it" in str(e)
            else:
                raise SystemExit("computed a digest without cns")
        print('ok')
    """))


def test_importing_the_package_does_not_load_cns_even_when_it_is_installed():
    ok(run("""
        import sys
        import alpha, alpha.cns_connector
        assert not [m for m in sys.modules if m == "cns" or m.startswith("cns.")], "cns was loaded"
        print('ok')
    """, block=False))


def test_no_module_of_the_package_imports_cns_by_statement():
    offenders = {}
    modules = sorted(PACKAGE.glob("*.py"))
    assert "cns_connector.py" in [p.name for p in modules]
    for path in modules:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module] if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module else []
            bad = [n for n in names if n == "cns" or n.startswith("cns.")]
            if bad:
                offenders.setdefault(path.name, []).extend(bad)
    assert offenders == {}


def _toml_list(section: str, key: str) -> list:
    """The quoted items of ``key = [...]`` inside ``[section]``; a text check, as tomllib is 3.11+."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    body, inside = [], False
    for line in text.splitlines():
        header = re.match(r"^\[([^\]]+)\]\s*$", line)
        if header:
            inside = header.group(1).strip() == section
        elif inside:
            body.append(line)
    found = re.search(r"^%s\s*=\s*\[(.*?)\]\s*$" % re.escape(key), "\n".join(body), re.S | re.M)
    assert found, f"{key} not found in [{section}]"
    return re.findall(r'"([^"]*)"', re.sub(r"#[^\n]*", "", found.group(1)))


def test_cns_is_not_a_runtime_dependency_and_the_cns_extra_is_pinned():
    runtime = _toml_list("project", "dependencies")
    assert any(re.match(r"\s*zeta\b", d) for d in runtime), runtime       # the existing dependency is kept
    assert not [d for d in runtime if re.match(r"\s*cns\b", d, re.I)], runtime
    assert _toml_list("project.optional-dependencies", "cns") == ["cns @ git+https://github.com/wking53214/CNS.git@v1.9.0"]
    assert not [d for d in _toml_list("project.optional-dependencies", "dev") if re.match(r"\s*cns\b", d, re.I)]
