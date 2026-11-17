"""A body's time series from CSV files, as FlexFlow Analyzer exports them."""
import pandas as pd
import pytest

from flowreel.project import PROJECT_FILE, load_project
from flowreel.project.bodies import Series
from flowreel.project.names import DeclaredSource
from flowreel.project.series import read_series

from conftest import ToySource

# `data table CASE --var aleDisp_y --node 24 --output disp.csv` writes tsId, time, values;
# a restart repeats time 0.2, and the later row wins.
ANALYZER = """tsId,time,aleDisp_y
1,0.1,0.010
2,0.2,0.020
3,0.3,0.030
2,0.2,0.025
"""


def write(folder, name, text):
    path = folder / name
    path.write_text(text)
    return path


def test_analyzer_csv(tmp_path):
    frame = read_series(Series("disp", write(tmp_path, "disp.csv", ANALYZER)))
    assert list(frame.columns) == ["time", "tsId", "aleDisp_y"]
    assert frame["time"].tolist() == [0.1, 0.2, 0.3]
    assert frame["aleDisp_y"].tolist() == [0.010, 0.025, 0.030]


def test_time_column_and_names(tmp_path):
    path = write(tmp_path, "f.csv", "t, Fy, Fx\n0.5, 2.0, 1.0\n0.0, 4.0, 3.0\n")
    frame = read_series(Series("force", path, time="t", columns={"lift": "Fy", "drag": "Fx"}))
    assert list(frame.columns) == ["time", "lift", "drag"]
    assert frame.to_dict("list") == {"time": [0.0, 0.5], "lift": [4.0, 2.0], "drag": [3.0, 1.0]}


def test_missing_file_and_column(tmp_path):
    with pytest.raises(FileNotFoundError, match="series 'disp': no such file"):
        read_series(Series("disp", tmp_path / "none.csv"))
    path = write(tmp_path, "disp.csv", ANALYZER)
    with pytest.raises(ValueError, match=r"disp.csv: series 'disp': no column 't' \(columns: tsId, time, aleDisp_y\)"):
        read_series(Series("disp", path, time="t"))
    with pytest.raises(ValueError, match="no column 'aleDisp_x'"):
        read_series(Series("disp", path, columns={"dx": "aleDisp_x"}))


PROJECT = """\
bodies:
  riser: {zone: cyl, axis: x, series: {displacement: data/riser.csv, force: data/force.csv}}
  ball: {zone: ball, series: {force: data/ball.csv}}
"""


class Zones(ToySource):
    def bodies(self):
        return ["cyl", "ball", "plate"]

    def series(self, name):
        if name != "probe":
            raise KeyError(f"toy source has no series {name!r}")
        return pd.DataFrame({"time": [0.0], "value": [7.0]})


@pytest.fixture
def source(tmp_path):
    (tmp_path / "data").mkdir()
    write(tmp_path / "data", "riser.csv", ANALYZER)
    write(tmp_path / "data", "force.csv", "time,fy\n0,1\n")
    write(tmp_path / "data", "ball.csv", "time,fy\n0,2\n")
    write(tmp_path, PROJECT_FILE, PROJECT)
    return DeclaredSource(Zones(), load_project(tmp_path).bodies)


def test_series_by_body(source):
    assert source.series("displacement", body="riser")["aleDisp_y"].iloc[-1] == 0.030
    assert source.series("force", body="cyl")["fy"].tolist() == [1]      # by zone too
    assert source.series("force", body="ball")["fy"].tolist() == [2]
    assert source.series("displacement")["time"].tolist() == [0.1, 0.2, 0.3]   # the only one


def test_series_errors_say_what_there_is(source):
    with pytest.raises(KeyError, match="declared for riser, ball: say which with body="):
        source.series("force")
    with pytest.raises(KeyError, match=r"body 'ball' has no series 'displacement' \(series: force\)"):
        source.series("displacement", body="ball")
    with pytest.raises(KeyError, match="'plate' is not declared, so it has no series"):
        source.series("force", body="plate")
    with pytest.raises(KeyError, match="no body 'rizer'"):
        source.series("force", body="rizer")


def test_undeclared_series_fall_back_to_the_source(source):
    assert source.series("probe")["value"].tolist() == [7.0]


def test_a_series_is_read_once(source, tmp_path):
    first = source.series("displacement", body="riser")
    (tmp_path / "data" / "riser.csv").unlink()
    first.loc[0, "aleDisp_y"] = 99.0                 # a copy: the cache is not touched
    assert source.series("displacement", body="riser")["aleDisp_y"].iloc[0] == 0.010
