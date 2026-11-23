"""flowreel project sections (Phase 8, branch 12): a body's sectional force along its
axis, step by step, as a series, on the generated cylinder case of the flow panels."""
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

MU = 0.5


@pytest.fixture
def project(tmp_path, monkeypatch):
    folder = case.write_case(tmp_path)
    data = yaml.safe_load((folder / "flowreel.yml").read_text()) or {}
    data["reference"] = {"rho": 2.0, "u_inf": 1.0}                  # q = 1
    (folder / "flowreel.yml").write_text(yaml.safe_dump(data))
    monkeypatch.chdir(folder)
    return folder


def run(line):
    return Shell(Path.cwd()).run(line)


def test_the_series_holds_each_steps_sections_and_their_stations(project):
    status, out, err = run(f"project sections plt:case --param mu={MU} --sections 8")
    assert status == 0, err
    table = pd.read_csv(project / "series" / "cylinder_sections.csv")
    assert list(table.columns) == ["time", "section", "fx", "fy", "fz", "cx", "cy", "cz"]
    assert table["time"].nunique() == case.STEPS and table["section"].nunique() == 8
    stations = pd.read_csv(project / "series" / "cylinder_sections_stations.csv")
    assert stations["station"].to_numpy() == pytest.approx(case.SPAN / 8 * (np.arange(8) + 0.5),
                                                          abs=1e-6)
    assert "by: section" in out and "stations: series/cylinder_sections_stations.csv" in out


def test_the_force_is_the_pressure_on_each_section(project):
    """The case's pressure rises across the flow, p = z: on a section of radius R it
    pushes with -pi R^2 dp/dz per unit length in z. Its shear along the axis cancels
    round the body, and the rotation of the flow is a solid one, with no shear."""
    assert run(f"project sections plt:case --param mu={MU} --sections 4")[0] == 0
    table = pd.read_csv(project / "series" / "cylinder_sections.csv")
    expected = -math.pi * case.RADIUS**2 * case.SLOPE
    assert table["fz"].to_numpy() == pytest.approx(expected, rel=0.03)
    assert np.abs(table["fx"]).max() < 0.02 * abs(expected)
    # coefficients: per length / (q D), q = 1, D = 1 (declared)
    assert table["cz"].to_numpy() == pytest.approx(table["fz"].to_numpy() / 1.0)


def test_a_second_run_keeps_the_steps_it_has(project):
    first = sorted(case_steps())[:2]
    assert run(f"project sections plt:case --param mu={MU} --sections 4 "
               f"--steps {first[0]} {first[1]}")[0] == 0
    path = project / "series" / "cylinder_sections.csv"
    before = pd.read_csv(path)
    status, out, _ = run(f"project sections plt:case --param mu={MU} --sections 4")
    assert status == 0 and f"{case.STEPS - 2} of {case.STEPS} steps to compute" in out
    after = pd.read_csv(path)
    assert after["time"].nunique() == case.STEPS
    kept = after[after["time"].isin(before["time"])].reset_index(drop=True)
    pd.testing.assert_frame_equal(kept, before)
    status, _, err = run(f"project sections plt:case --param mu={MU} --sections 6")
    assert status != 0 and "has 4 sections, not 6" in err


def case_steps():
    from flowreel.sources.plt import PltSource
    return PltSource(Path.cwd() / "case").steps()


def test_the_series_reads_back_as_the_bodys_series(project):
    """Declared as the command says, the series is what a map panel draws."""
    assert run(f"project sections plt:case --param mu={MU} --sections 4")[0] == 0
    data = yaml.safe_load((project / "flowreel.yml").read_text())
    data["bodies"]["cylinder"]["series"] = {"sections": {
        "file": "series/cylinder_sections.csv", "by": "section",
        "stations": "series/cylinder_sections_stations.csv"}}
    (project / "flowreel.yml").write_text(yaml.safe_dump(data))
    from flowreel.project import load_project
    from flowreel.project.series import read_series
    spec = load_project(project / "flowreel.yml").bodies["cylinder"].series["sections"]
    frame = read_series(spec)
    assert list(frame.columns[:3]) == ["time", "section", "station"]
    assert len(frame) == case.STEPS * 4


@pytest.mark.parametrize("line, message", [
    ("project sections plt:case --sections 4", "mu"),
    ("project sections plt:case --param mu --sections 4", "KEY=NUMBER"),
    ("project sections plt:case --param mu=1 --steps 9000 9100", "no saved step"),
    ("project sections plt:case --param mu=1 --body mast", "mast"),
])
def test_errors_say_what_is_missing(project, line, message):
    status, _, err = run(line)
    assert status != 0 and message in err, err
