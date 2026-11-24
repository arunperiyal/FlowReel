"""A small project with histories at many points, for the span panels."""
import numpy as np
import yaml

T = np.array([0.0, 1.0, 2.0, 3.0])
NODES = {1: 0.0, 2: 5.0, 3: 10.0}          # node: station


def lift(t, s):
    return np.sin(t) * s / 10              # 0 at station 0, |value| <= 1


def project(folder):
    """A project of one tag, ``t``, whose ``domain.yml`` declares a pipe 10 long (pinned at
    0, roller with tension at 10) with lift and dy at three nodes, one CSV per node; a rod
    with lift in one long CSV (no stations); and the pipe's force at one point. The CSV
    files are in the tag's folder, ``data/t``."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "flowreel.yml").write_text("tags: [t]\n")
    data = folder / "data" / "t"
    data.mkdir(parents=True, exist_ok=True)
    bodies = {"pipe": {"axis": "x",
                       "ends": [{"at": 0, "support": "pinned"},
                                {"at": 10, "support": "roller", "free_along": "x", "tension": True}],
                       "series": {"span": {"file": "pipe_{node}.csv", "by": "node",
                                           "stations": "nodes.csv"},
                                  "force": "force.csv"}},
              "rod": {"axis": "x", "series": {"span": {"file": "rod.csv", "by": "node"}}}}
    (data / "domain.yml").write_text(yaml.safe_dump(
        {"kind": "geometry", "source": {"body": "grooved_cylinder"}, "bodies": bodies}))
    (data / "nodes.csv").write_text("node,station\n" + "".join(f"{n},{s}\n" for n, s in NODES.items()))
    for n, s in NODES.items():
        rows = "".join(f"{t},{lift(t, s)},{0.1 * s * t}\n" for t in T)
        (data / f"pipe_{n}.csv").write_text("time,cl,dy\n" + rows)
    (data / "rod.csv").write_text("time,node,cl\n" + "".join(
        f"{t},{n},{2 * t + n}\n" for t in T for n in (1, 2)))
    (data / "force.csv").write_text("time,f\n0,1\n1,2\n")
    return folder
