"""flowreel data extract sections (Phase 9, branch 4): a body's sectional force along its
axis, step by step, written into the tag and declared under its body, on the generated
cylinder case of the flow panels (the tests of PR #84, on a tag)."""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "examples" / "flow_panels"))
import cylinder_case as case  # noqa: E402

from cli_harness import Shell  # noqa: E402
from flowreel.project.domain import load_domain  # noqa: E402

UNITS = {"rho": 2.0, "u_inf": 1.0, "mu": 0.5}                    # q = 1


def make_tag(root, units=UNITS, bodies=None):
    case.write_case(root.parent / "cases")
    folder = root / "data" / "bare"
    folder.mkdir(parents=True)
    (folder / "plt").symlink_to(root.parent / "cases" / "case", target_is_directory=True)
    (folder / "domain.yml").write_text(yaml.safe_dump({
        "kind": "plt", "source": {"path": "plt"}, "units": units,
        "bodies": bodies or {"cyl": {"zone": "cyl", "axis": "x", "diameter": 1.0}}},
        sort_keys=False))
    return folder


@pytest.fixture
def tag(tmp_path, monkeypatch):
    root = tmp_path / "film"
    root.mkdir()
    (root / "flowreel.yml").write_text("")
    monkeypatch.chdir(root)
    return make_tag(root)


def run(line):
    return Shell(Path.cwd()).run(line)


def steps():
    from flowreel.sources.plt import PltSource
    return PltSource(Path.cwd() / "data" / "bare" / "plt").steps()


def test_the_series_is_written_into_the_tag_and_declared(tag):
    status, out, err = run("data extract sections bare --sections 8")
    assert status == 0, err
    table = pd.read_csv(tag / "series" / "cyl_sections.csv")
    assert list(table.columns) == ["time", "section", "fx", "fy", "fz", "cx", "cy", "cz"]
    assert table["time"].nunique() == case.STEPS and table["section"].nunique() == 8
    stations = pd.read_csv(tag / "series" / "cyl_sections_stations.csv")
    assert stations["station"].to_numpy() == pytest.approx(case.SPAN / 8 * (np.arange(8) + 0.5),
                                                          abs=1e-6)
    assert "declared as cyl's sections in data/bare/domain.yml" in out
    from flowreel.project.series import read_series
    frame = read_series(load_domain(tag).bodies["cyl"].series["sections"])
    assert list(frame.columns[:3]) == ["time", "section", "station"]
    assert len(frame) == case.STEPS * 8


def test_the_force_is_the_pressure_on_each_section(tag):
    """The case's pressure rises across the flow, p = z: on a section of radius R it
    pushes with -pi R^2 dp/dz per unit length in z. Its shear along the axis cancels
    round the body, and the rotation of the flow is a solid one, with no shear."""
    assert run("data extract sections bare --sections 4")[0] == 0
    table = pd.read_csv(tag / "series" / "cyl_sections.csv")
    expected = -math.pi * case.RADIUS**2 * case.SLOPE
    assert table["fz"].to_numpy() == pytest.approx(expected, rel=0.03)
    assert np.abs(table["fx"]).max() < 0.02 * abs(expected)
    # coefficients: per length / (q D), q = 1/2 rho u_inf^2 = 1 from the tag's units, D = 1
    assert table["cz"].to_numpy() == pytest.approx(table["fz"].to_numpy())


def test_a_second_run_keeps_the_steps_it_has(tag):
    first = sorted(steps())[:2]
    assert run(f"data extract sections bare --sections 4 --steps {first[0]} {first[1]}")[0] == 0
    path = tag / "series" / "cyl_sections.csv"
    before = pd.read_csv(path)
    status, out, _ = run("data extract sections bare --sections 4")
    assert status == 0 and f"{case.STEPS - 2} of {case.STEPS} steps to compute" in out
    assert "was declared already" in out
    after = pd.read_csv(path)
    kept = after[after["time"].isin(before["time"])].reset_index(drop=True)
    pd.testing.assert_frame_equal(kept, before)
    status, _, err = run("data extract sections bare --sections 6")
    assert status != 0 and "has 4 sections, not 6" in err
    status, out, err = run("data extract sections bare --sections 6 --force")
    assert status == 0, err
    assert pd.read_csv(path)["section"].nunique() == 6


def test_a_hand_written_declaration_is_replaced_only_with_force(tag):
    text = (tag / "domain.yml").read_text().replace(
        "    diameter: 1.0\n", "    diameter: 1.0\n    series:\n      sections: {file: mine.csv}\n")
    (tag / "domain.yml").write_text(text)
    status, _, err = run("data extract sections bare --sections 4")
    assert status != 0 and "--force" in err
    assert run("data extract sections bare --sections 4 --force")[0] == 0
    assert load_domain(tag).bodies["cyl"].series["sections"].file.name == "cyl_sections.csv"


def test_no_coefficients_without_the_diameter(tmp_path, monkeypatch):
    root = tmp_path / "film"
    root.mkdir()
    (root / "flowreel.yml").write_text("")
    monkeypatch.chdir(root)
    folder = make_tag(root, bodies={"cyl": {"zone": "cyl", "axis": "x"}})
    status, out, _ = run("data extract sections bare --sections 4")
    assert status == 0 and "no coefficients" in out
    assert "cz" not in pd.read_csv(folder / "series" / "cyl_sections.csv").columns


@pytest.mark.parametrize("line, units, message", [
    ("data extract sections bare", {"rho": 1.0}, "units.mu"),
    ("data extract sections bare --steps 9000 9100", UNITS, "no saved step"),
    ("data extract sections bare --body mast", UNITS, "no body 'mast'"),
    ("data extract sections nobody", UNITS, "no tag 'nobody'"),
    ("data extract sections bare --sections 0", UNITS, "at least 1"),
])
def test_errors_say_what_is_missing(tmp_path, monkeypatch, line, units, message):
    root = tmp_path / "film"
    root.mkdir()
    (root / "flowreel.yml").write_text("")
    monkeypatch.chdir(root)
    make_tag(root, units=units)
    status, _, err = run(line)
    assert status != 0 and message in err, err
