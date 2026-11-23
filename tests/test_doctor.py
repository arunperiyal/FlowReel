"""flowreel doctor: the report of what FlowReel runs on (flowreel.doctor)."""
import tomllib
from pathlib import Path

from flowreel import doctor as D

ROOT = Path(__file__).parent.parent


def test_the_oldest_tested_versions_are_the_declared_minimums():
    """CI's oldest job installs the minimums of pyproject.toml; TESTED says the same."""
    declared = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["dependencies"]
    for name, (oldest, newest) in D.TESTED.items():
        line = next(d for d in declared if d.lower().startswith(name + ">="))
        assert line.split(">=")[1] == oldest, (name, line)
        assert D.version_tuple(newest) >= D.version_tuple(oldest)


def test_versions_are_read_as_numbers():
    assert D.version_tuple("9.7.2") == (9, 7, 2)
    assert D.version_tuple("2.1.1rc1") == (2, 1, 1)
    assert D.version_tuple("0.49.dev0") == (0, 49)


def test_the_minimums_are_read_from_the_installed_package():
    found = D.minimums()
    assert found["vtk"] == "9.3" and found["numpy"] == "1.26" and "pytest" not in found
