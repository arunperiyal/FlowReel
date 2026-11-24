"""A small project with declared series, for panel tests."""
import numpy as np
import yaml

T = np.arange(0, 2.01, 0.5)                   # 0, 0.5, 1, 1.5, 2


def project(folder):
    """A project of one tag, ``t``, whose ``domain.yml`` declares the bodies bare and
    helical (series force: cl, cd; motion: y) and a span history (by node) for helical;
    the CSV files are in the tag's folder."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "flowreel.yml").write_text("tags: [t]\n")
    tag = folder / "data" / "t"
    tag.mkdir(parents=True, exist_ok=True)
    bodies = {"bare": {"series": {"force": {"file": "bare_force.csv", "columns": {"cl": "CL", "cd": "CD"}},
                                  "motion": "bare_motion.csv"}},
              "helical": {"series": {"force": {"file": "hel_force.csv", "columns": {"cl": "CL", "cd": "CD"}},
                                     "span": {"file": "hel_span.csv", "by": "node"}}}}
    (tag / "domain.yml").write_text(yaml.safe_dump(
        {"kind": "geometry", "source": {"body": "grooved_cylinder"}, "bodies": bodies}))
    rows = "\n".join(f"{t},{t * 2},{1 + t}" for t in T)       # CL = 2t, CD = 1 + t
    (tag / "bare_force.csv").write_text("time,CL,CD\n" + rows + "\n")
    rows = "\n".join(f"{t},{-t},{1}" for t in T)               # CL = -t, CD = 1
    (tag / "hel_force.csv").write_text("time,CL,CD\n" + rows + "\n")
    rows = "\n".join(f"{t},{t * t}" for t in T)                # y = t^2
    (tag / "bare_motion.csv").write_text("time,y\n" + rows + "\n")
    (tag / "hel_span.csv").write_text("time,node,y\n0,1,0\n0,2,0\n")
    return folder
