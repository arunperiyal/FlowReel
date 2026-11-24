"""The ``bodies:`` schema of a tag's ``domain.yml``, and finding a shot's project."""
from pathlib import Path

import pytest

from flowreel.project import PROJECT_FILE, find_project, load_project, project_for
from flowreel.project.bodies import Body, End, parse_bodies
from flowreel.project.domain import load_domain
from flowreel.scene.errors import Checker, ConfigError

RISER = """\
bodies:
  riser:
    zone: cyl
    axis: x
    diameter: 1.0
    ends:
      - {at: 0.0, support: pinned}
      - {at: 500.0, support: roller, free_along: x, tension: true}
    series:
      displacement: {file: data/riser_disp.csv, by: node, stations: data/riser_nodes.csv}
      force: data/riser_force.csv
  downstream:
    zone: cyl2
    axis: x
    ends: [{at: 0.0, support: clamped}, {at: 12.0, support: clamped}]
  sphere: {}
"""


def write(folder: Path, text: str) -> Path:
    path = folder / PROJECT_FILE
    path.write_text(text)
    return path


def bodies(value):
    return parse_bodies(value, Checker("flowreel.yml", ("bodies",)), Path("/p"))


def test_full_declaration(tmp_path):
    folder = tmp_path / "data" / "t"
    folder.mkdir(parents=True)
    (folder / "domain.yml").write_text("kind: geometry\nsource: {body: grooved_cylinder}\n" + RISER)
    declared = load_domain(folder).bodies
    riser = declared["riser"]
    assert riser == Body("riser", "cyl", "x", 1.0, (
        End(0.0, "pinned"), End(500.0, "roller", True, {"free_along": "x"})), riser.series)
    disp = riser.series["displacement"]
    assert disp.file == folder.resolve() / "data/riser_disp.csv" and disp.by == "node"
    assert disp.stations == folder.resolve() / "data/riser_nodes.csv" and disp.time == "time"
    assert riser.series["force"].file.name == "riser_force.csv"
    assert declared["downstream"].diameter is None
    sphere = declared["sphere"]
    assert sphere.zone == "sphere" and sphere.axis is None and sphere.ends == ()


def test_support_options():
    b = bodies({"b": {"axis": "z", "ends": [
        {"at": 0, "support": "spring", "stiffness": 20},
        {"at": 1, "support": "free", "mark": True},
        {"at": 2, "support": "prescribed", "direction": [0, 1, 0]},
        {"at": 3, "support": "prescribed", "direction": "y"}]}})["b"]
    assert [e.options for e in b.ends] == [{"stiffness": 20.0}, {"mark": True},
                                           {"direction": (0.0, 1.0, 0.0)}, {"direction": "y"}]


def test_stations_as_numbers():
    s = bodies({"b": {"series": {"d": {"file": "d.csv", "by": "node", "stations": [0, 2.5]},
                                 "f": {"file": "/abs/f.csv", "columns": {"lift": "Fy"}}}}})["b"].series
    assert s["d"].stations == (0.0, 2.5) and s["d"].file == Path("/p/d.csv")
    assert s["f"].file == Path("/abs/f.csv") and s["f"].columns == {"lift": "Fy"}


@pytest.mark.parametrize("value, msg", [
    ({"b": {"zon": "c"}}, r"bodies\.b\.zon: unknown key .*did you mean 'zone'"),
    ({"b": {"axis": "w"}}, r"bodies\.b\.axis: 'w' is not allowed"),
    ({"b": {"axis": "x", "diameter": 0}}, r"bodies\.b\.diameter: must be positive"),
    ({"b": {"diameter": 1}}, r"bodies\.b\.diameter: a diameter is for a beam body"),
    ({"b": {"ends": [{"at": 0, "support": "pinned"}]}}, r"bodies\.b\.ends: .*give the body an 'axis'"),
    ({"b": {"axis": "x", "ends": [{"at": 0, "support": "pined"}]}},
     r"ends\[0\]\.support: .*did you mean 'pinned'"),
    ({"b": {"axis": "x", "ends": [{"at": 0, "support": "roller"}]}},
     r"ends\[0\]: missing key 'free_along'"),
    ({"b": {"axis": "x", "ends": [{"at": 0, "support": "pinned", "stiffness": 1}]}},
     r"ends\[0\]\.stiffness: unknown key"),
    ({"b": {"axis": "x", "ends": [{"at": 0, "support": "spring", "stiffness": -1}]}},
     r"stiffness: must be positive"),
    ({"b": {"axis": "x", "ends": [{"at": 1, "support": "pinned"}, {"at": 1, "support": "free"}]}},
     r"ends: two supports at the same station"),
    ({"b": {"axis": "x", "ends": [{"at": 0}]}}, r"ends\[0\]: expected \{at: STATION, support: KIND\}"),
    ({"b": {"series": {"d": {"by": "node"}}}}, r"series\.d: missing key 'file'"),
    ({"b": {"series": {"d": {"file": "d.csv", "stations": [1]}}}}, r"stations: .*give 'by'"),
    ({"a": {"zone": "c"}, "b": {"zone": "c"}}, r"bodies\.b\.zone: zone 'c' is already the body 'a'"),
    (["riser"], r"bodies: expected a mapping"),
])
def test_errors_name_the_key(value, msg):
    with pytest.raises(ConfigError, match=msg):
        bodies(value)


def test_the_keys_of_flowreel_yml(tmp_path):
    with pytest.raises(ConfigError, match=r"flowreel.yml: bodies: unknown key .*allowed: defaults, tags"):
        load_project(write(tmp_path, "bodies: {}\n"))
    with pytest.raises(ConfigError, match=r"flowreel.yml: reference: unknown key"):
        load_project(write(tmp_path, "reference: {rho: 1}\n"))
    with pytest.raises(ConfigError, match=r"flowreel.yml: tgs: unknown key .*'tags'"):
        load_project(write(tmp_path, "tgs: []\n"))


def test_empty_file_is_an_empty_project(tmp_path):
    assert load_project(write(tmp_path, "")).tag_names == ()
    assert load_project(tmp_path).tags == {}


def test_a_shot_finds_the_nearest_project(tmp_path):
    write(tmp_path, "tags: [top]\n")
    (tmp_path / "shots" / "close").mkdir(parents=True)
    shot = tmp_path / "shots" / "close" / "a.yml"
    shot.write_text("")
    assert find_project(shot) == (tmp_path / PROJECT_FILE).resolve()
    assert project_for(shot).tag_names == ("top",)
    write(tmp_path / "shots", "tags: [near]\n")
    assert project_for(shot).tag_names == ("near",)
    assert project_for(None) is None


def test_no_project(tmp_path):
    assert find_project(tmp_path) is None
