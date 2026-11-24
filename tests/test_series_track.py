"""Series tracks: a number from a time series at each frame's time, exact values."""
import pickle

import numpy as np
import pandas as pd
import pytest

from flowreel import tracks
from flowreel.scene.errors import ConfigError
from flowreel.scene.rendering import Scene
from flowreel.scene.shot import from_dict
from flowreel.tracks import SeriesTrack

from conftest import ToySource
from tag_fixture import declare_bodies
from test_render import VIEWS


class Series:
    """A stand-in source: two series, one at two stations."""

    name = "s"

    def series(self, name, body=None):
        if name == "force":
            return pd.DataFrame({"time": [0.0, 1.0, 2.0], "fy": [0.0, 10.0, 20.0]})
        if name == "both":
            return pd.DataFrame({"time": [0.0, 1.0], "fx": [1.0, 1.0], "fy": [0.0, 2.0]})
        if name == "disp":
            frame = pd.DataFrame({"time": [0.0, 0.0, 1.0, 1.0], "node": [0, 1, 0, 1],
                                  "station": [0.0, 10.0, 0.0, 10.0], "dy": [0.0, 2.0, 0.0, 4.0]})
            frame.attrs["by"] = "node"
            return frame
        raise KeyError(f"no series {name!r}")


def test_value_at_the_frame_time_scaled_and_offset():
    track = tracks.parse({"series": "force", "scale": 2, "offset": 1}, "number", "length")
    assert isinstance(track, SeriesTrack) and not track.bound
    track.bind(Series(), [0.5, 1.5, 3.0, -1.0])
    assert [track.at(i) for i in range(4)] == [11.0, 31.0, 41.0, 1.0]   # held outside
    assert track.at(0.5) == 21.0 and track(1) == 31.0                   # between frames


def test_columns_and_stations():
    assert SeriesTrack("both", "fy").bind(Series(), [0.5]).at(0) == 1.0
    with pytest.raises(ValueError, match="has columns fx, fy; give 'column'"):
        SeriesTrack("both").bind(Series(), [0.5])
    with pytest.raises(ValueError, match="has no column 'fz'"):
        SeriesTrack("both", "fz").bind(Series(), [0.5])
    mid = SeriesTrack("disp", station=5.0).bind(Series(), [0.0, 0.5, 1.0])
    assert [mid.at(i) for i in range(3)] == [1.0, 1.5, 2.0]
    with pytest.raises(ValueError, match="at many stations; give 'station'"):
        SeriesTrack("disp").bind(Series(), [0.0])
    with pytest.raises(ValueError, match="has no stations"):
        SeriesTrack("force", station=1.0).bind(Series(), [0.0])


@pytest.mark.parametrize("spec, kind, msg", [
    ({"series": "f", "colum": "a"}, "number", "unknown key 'colum' in a series track"),
    ({"series": "f", "scale": "big"}, "number", r"length.scale: expected a number"),
    ({"series": 3}, "number", "series must be a name"),
    ({"series": "f"}, "colour", "a series track gives numbers; length is a colour"),
])
def test_parse_errors(spec, kind, msg):
    with pytest.raises(ValueError, match=msg):
        tracks.parse(spec, kind, "length")


def test_unbound_and_pickled():
    track = SeriesTrack("force")
    with pytest.raises(RuntimeError, match="no values until the shot's source is opened"):
        track.at(0)
    bound = track.bind(Series(), [1.0])
    assert not pickle.loads(pickle.dumps(bound)).bound


class Riser(ToySource):
    def bodies(self):
        return ["cyl"]


BODIES = "bodies: {riser: {zone: cyl, axis: z, series: {force: data/force.csv}}}\n"


def shot(tmp_path, length):
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "force.csv").write_text("time,fy\n0,0\n1,4\n")
    spec = {"name": "s", "source": "toy", "time": {"steps": [0, 20]},
            "camera": {"view": "main"}, "size": [64, 48], "antialias": "none",
            "layers": [{"type": "markers3d", "shape": "arrow3d", "at": [0, 0, 0],
                        "length": length}]}
    return from_dict(spec, file=str(tmp_path / "s.yml"))


def test_a_shot_binds_its_series_tracks(tmp_path):
    # ToySource steps 0, 10, 20 are at times 0, 0.5, 1.0
    scene = Scene.make(shot(tmp_path, {"series": "force", "body": "riser", "scale": 0.5}),
                       declare_bodies(Riser(), BODIES, tmp_path), VIEWS)
    assert [scene.values(i)[0]["length"] for i in range(3)] == [0.0, 1.0, 2.0]


def test_a_wrong_series_names_the_layer(tmp_path):
    with pytest.raises(ConfigError, match=r"s.yml: layers\[0\]\.length: .*no series 'lift'"):
        Scene.make(shot(tmp_path, {"series": "lift", "body": "riser"}),
                   declare_bodies(Riser(), BODIES, tmp_path), VIEWS)
