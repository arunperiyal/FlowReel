"""FlexFlow histories into a tag (Phase 9, branch 3): OTHD and OISD files read as FlexFlow
Analyzer reads them (run order, restarts, groups), a CSV a group, declared under bodies."""
import json
import sys
from pathlib import Path

import pytest

from cli_harness import Shell
from flowreel.project import history as H
from flowreel.project.domain import load_domain

sys.path.insert(0, str(Path(__file__).parent.parent / "examples" / "flow_panels"))
import cylinder_case as case  # noqa: E402

NODES = 3


def disp(group, t, node):
    """The generated displacement: tells group, time and node apart."""
    return (0.0, 10 * group + t + 0.01 * node, -t)


def othd_text(times, groups, run=0):
    """OTHD records at ``times``, each group's aleDisp block (``run`` added to dy, so a
    restart's values differ from the run before), and the pendulum's inline line."""
    out = []
    for k, t in enumerate(times):
        out += [f"tsId {k + 1}", f"time {t}"]
        for g in groups:
            out += [f"othId {g}", f"aleDisp 3 {NODES}"]
            out += [" ".join(f"{v + (run if i == 1 else 0):.6f}" for i, v in enumerate(disp(g, t, n)))
                    for n in range(NODES)]
        out.append(f"avePres {0.5 * t}")
    return "\n".join(out) + "\n"


def oisd_text(times, groups):
    out = []
    for k, t in enumerate(times):
        out += [f"tsId {k + 1}", f"time {t}"]
        for g in groups:
            out += [f"osgId {g}", f"totArea {1.0 + g}", "totTrac 3 1", f"{t} {g + 2 * t} 0.0"]
    return "\n".join(out) + "\n"


def write_case(folder, groups=(0,), restart=True):
    """``othd_files/`` with two runs (run 2 resumed at t=0.2 and wrote 0.2 again) in the
    archive layout, and ``oisd_files/`` flat."""
    othd = folder / "othd_files" / "archive"
    othd.mkdir(parents=True)
    (othd / "riser1.othd").write_text(othd_text([0.0, 0.1, 0.2], groups))
    if restart:
        (othd / "riser2.othd").write_text(othd_text([0.2, 0.3], groups, run=100))
    oisd = folder / "oisd_files"
    oisd.mkdir()
    (oisd / "riser1.oisd").write_text(oisd_text([0.0, 0.1, 0.2, 0.3], groups))
    return folder


@pytest.fixture
def project(tmp_path, monkeypatch):
    root = tmp_path / "film"
    root.mkdir()
    (root / "flowreel.yml").write_text("")
    case.write_case(tmp_path / "flow", project=False)
    monkeypatch.chdir(root)
    assert Shell(root).run(f"data import plt --path {tmp_path / 'flow' / 'case'} --tag bare")[0] == 0
    return root


def run(line):
    return Shell(Path.cwd()).run(line)


def test_run_order_and_the_runs_record(tmp_path):
    folder = tmp_path / "othd_files"
    for sub, n in (("archive", 1), ("archive", 3), ("cleaned", 2), ("archive", 10)):
        (folder / sub).mkdir(parents=True, exist_ok=True)
        (folder / sub / f"riser{n}.othd").write_text("")
    assert [p.name for p in H.run_files(folder, "othd")] == \
        ["riser1.othd", "riser2.othd", "riser3.othd", "riser10.othd"]       # 10 after 3
    (folder / "cleaned" / ".runs.json").write_text(json.dumps({"cleaned": {"2": 3}, "skipped": [10]}))
    files = H.run_files(folder, "othd")                                    # cleaned 2 is run 3
    assert [f"{p.parent.name}/{p.name}" for p in files] == ["archive/riser1.othd", "archive/riser3.othd"]
    only = tmp_path / "compiled"
    only.mkdir()
    (only / "riser.othd").write_text("")
    assert [p.name for p in H.run_files(only, "othd")] == ["riser.othd"]


def test_a_restart_takes_the_later_run_and_groups_stay_apart(tmp_path):
    folder = write_case(tmp_path / "run", groups=(0, 1))
    groups = H.read_history(H.run_files(folder / "othd_files", "othd"))
    assert set(groups) == {0, 1}
    frame = H.table(groups[1])
    assert list(frame.columns) == ["time", "node", "aleDisp_x", "aleDisp_y", "aleDisp_z", "avePres"]
    assert sorted(frame["time"].unique()) == [0.0, 0.1, 0.2, 0.3]           # 0.2 once
    at = frame[(frame.time == 0.2) & (frame.node == 2)].iloc[0]
    assert at.aleDisp_y == pytest.approx(10 + 0.2 + 0.02 + 100)            # run 2's
    at = frame[(frame.time == 0.1) & (frame.node == 0)].iloc[0]
    assert at.aleDisp_y == pytest.approx(10.1) and at.avePres == pytest.approx(0.05)
    one = H.table(H.read_history(H.run_files(folder / "oisd_files", "oisd"))[0])
    assert "node" not in one.columns and list(one.totTrac_y) == pytest.approx([0, 0.2, 0.4, 0.6])


def test_one_group_goes_to_the_one_body(project, tmp_path):
    write_case(tmp_path / "run")
    status, out, err = run(f"data import history --path {tmp_path / 'run'} --tag bare")
    assert status == 0, err
    assert "othd group 0: series/othd_0.csv, 12 rows, 3 nodes; declared as cyl's displacement" in out
    assert "oisd group 0: series/oisd_0.csv, 4 rows; declared as cyl's force" in out
    folder = project / "data" / "bare"
    assert (folder / "othd").is_symlink() and (folder / "oisd").is_symlink()
    domain = load_domain(folder)
    assert set(domain.bodies["cyl"].series) == {"displacement", "force"}
    assert domain.measured["history"]["othd"]["files"] == ["riser1.othd", "riser2.othd"]
    assert "# domain.yml of the tag" in (folder / "domain.yml").read_text()     # comments kept
    from flowreel.project.series import read_series
    d = read_series(domain.bodies["cyl"].series["displacement"])
    assert {"dx", "dy", "dz", "node"} <= set(d.columns)
    f = read_series(domain.bodies["cyl"].series["force"])
    assert list(f.fy) == pytest.approx([0, 0.2, 0.4, 0.6])
    status, _, err = run(f"data import history --path {tmp_path / 'run'} --tag bare")
    assert status != 0 and "--force" in err
    assert run(f"data import history --path {tmp_path / 'run'} --tag bare --force")[0] == 0
    assert set(load_domain(folder).bodies["cyl"].series) == {"displacement", "force"}


def test_several_groups_are_listed_or_named(project, tmp_path):
    write_case(tmp_path / "run", groups=(0, 1))
    status, out, err = run(f"data import history --path {tmp_path / 'run'} --tag bare")
    assert status == 0, err
    text = (project / "data" / "bare" / "domain.yml").read_text()
    assert "# history groups not given to a body" in text and "#   othd 1 (displacement)" in text
    assert load_domain(project / "data" / "bare").bodies["cyl"].series == {}
    status, out, err = run(f"data import history --path {tmp_path / 'run'} --tag bare --force "
                           f"--group 1=cyl")
    assert status == 0, err
    domain = load_domain(project / "data" / "bare")
    assert domain.bodies["cyl"].series["displacement"].file.name == "othd_1.csv"
    assert "#   othd 0 (displacement)" in (project / "data" / "bare" / "domain.yml").read_text()
    status, _, err = run(f"data import history --path {tmp_path / 'run'} --tag bare --force "
                         f"--group 1=riser")
    assert status != 0 and "no body 'riser'" in err


def test_re_importing_the_flow_keeps_the_history(project, tmp_path):
    write_case(tmp_path / "run")
    run(f"data import history --path {tmp_path / 'run'} --tag bare")
    assert run(f"data import plt --path {tmp_path / 'flow' / 'case'} --tag bare --force")[0] == 0
    domain = load_domain(project / "data" / "bare")
    assert "othd" in domain.measured["history"] and "force" in domain.bodies["cyl"].series


@pytest.mark.parametrize("line, message", [
    ("data import history --path {run} --tag nobody", "import its flow first"),
    ("data import history --tag bare", "--path"),
    ("data import history --path {empty} --tag bare", "no .othd or .oisd"),
    ("data import history --path {run} --tag bare --group x=cyl", "group number"),
    ("data import plt --path {run} --tag bare --group 0=cyl", "for data import history"),
])
def test_errors(project, tmp_path, line, message):
    write_case(tmp_path / "run")
    (tmp_path / "empty").mkdir()
    status, _, err = run(line.format(run=tmp_path / "run", empty=tmp_path / "empty"))
    assert status != 0 and message in err, err


def test_declare_series_keeps_the_file_and_its_order(tmp_path):
    from flowreel.project.domain import declare_series
    folder = tmp_path / "data" / "t"
    folder.mkdir(parents=True)
    (folder / "domain.yml").write_text(
        "kind: plt  # mine\nbodies:\n  a:\n    zone: a   # wall\n    series:\n"
        "      lift: {file: l.csv}\n  b: {zone: b}\n")
    declare_series(folder, "a", "drag", {"file": "d.csv"})
    declare_series(folder, "b", "drag", {"file": "e.csv"})
    with pytest.raises(ValueError, match="--force"):
        declare_series(folder, "a", "lift", {"file": "x.csv"})
    declare_series(folder, "a", "lift", {"file": "x.csv"}, force=True)
    text = (folder / "domain.yml").read_text()
    assert "# mine" in text and "# wall" in text
    domain = load_domain(folder)
    assert list(domain.bodies["a"].series) == ["lift", "drag"]
    assert domain.bodies["a"].series["lift"].file.name == "x.csv"
    with pytest.raises(ValueError, match="no body 'c'"):
        declare_series(folder, "c", "lift", {"file": "x.csv"})
