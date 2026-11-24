"""A body's time series from CSV files, as FlexFlow Analyzer exports them."""
import pandas as pd
import pytest

from flowreel.project.bodies import Series
from flowreel.project.series import read_series

from conftest import ToySource
from tag_fixture import declare_bodies

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
    return declare_bodies(Zones(), PROJECT, tmp_path)


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


# -- histories at many points ------------------------------------------------------------

LONG = """time,node,dy
0.1,0,0.0
0.1,1,0.5
0.1,2,0.0
0.2,0,0.0
0.2,1,0.6
0.2,2,0.1
"""


def test_long_form_with_stations(tmp_path):
    path = write(tmp_path, "disp.csv", LONG)
    frame = read_series(Series("disp", path, by="node", stations=(0.0, 250.0, 500.0)))
    assert list(frame.columns) == ["time", "node", "station", "dy"]
    assert frame["station"].tolist() == [0.0, 250.0, 500.0] * 2
    assert frame[frame.time == 0.2]["dy"].tolist() == [0.0, 0.6, 0.1]
    plain = read_series(Series("disp", path, by="node"))
    assert list(plain.columns) == ["time", "node", "dy"]


def test_stations_from_a_file(tmp_path):
    path = write(tmp_path, "disp.csv", LONG)
    nodes = write(tmp_path, "nodes.csv", "node, station\n2, 500\n0, 0\n1, 250\n")
    frame = read_series(Series("disp", path, by="node", stations=nodes))
    assert frame["station"].tolist() == [0.0, 250.0, 500.0] * 2


def test_one_file_per_node(tmp_path):
    """FlexFlow Analyzer's `data table --node N --output disp_N.csv`, once per node."""
    for node, dy in ((0, 0.0), (12, 0.5), (24, 0.2)):
        write(tmp_path, f"disp_{node}.csv", f"tsId,time,aleDisp_y\n1,0.1,{dy}\n2,0.2,{dy * 2}\n")
    write(tmp_path, "disp_all.csv", "not, this\n")
    spec = Series("disp", tmp_path / "disp_{node}.csv", by="node", stations=(0.0, 6.0, 12.0),
                  columns={"dy": "aleDisp_y"})
    frame = read_series(spec)
    assert list(frame.columns) == ["time", "node", "station", "tsId", "dy"]
    assert frame["node"].tolist() == [0, 12, 24, 0, 12, 24]
    assert frame[frame.time == 0.2]["dy"].tolist() == [0.0, 1.0, 0.4]
    assert frame[frame.node == 24]["station"].tolist() == [12.0, 12.0]


@pytest.mark.parametrize("spec, msg", [
    (dict(by="probe"), "no column 'probe'"),
    (dict(by="node", stations=(0.0, 1.0)), r"2 stations for 3 points \(node 0 to 2\)"),
])
def test_point_errors(tmp_path, spec, msg):
    with pytest.raises(ValueError, match=msg):
        read_series(Series("disp", write(tmp_path, "disp.csv", LONG), **spec))


def test_station_file_errors(tmp_path):
    path = write(tmp_path, "disp.csv", LONG)
    short = write(tmp_path, "nodes.csv", "node,station\n0,0\n1,250\n")
    with pytest.raises(ValueError, match="no station for node 2"):
        read_series(Series("disp", path, by="node", stations=short))
    bad = write(tmp_path, "bad.csv", "node,where\n0,0\n")
    with pytest.raises(ValueError, match="no column 'station'"):
        read_series(Series("disp", path, by="node", stations=bad))
    with pytest.raises(FileNotFoundError, match="no file matches"):
        read_series(Series("disp", tmp_path / "x_{node}.csv", by="node"))
