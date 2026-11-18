"""A small project with declared series, for panel tests."""
import numpy as np

T = np.arange(0, 2.01, 0.5)                   # 0, 0.5, 1, 1.5, 2


def project(folder):
    """flowreel.yml with bodies bare and helical (series force: cl, cd; motion: y) and
    a span history (by node) for helical."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "flowreel.yml").write_text(
        "bodies:\n"
        "  bare:\n    series:\n      force: {file: bare_force.csv, columns: {cl: CL, cd: CD}}\n"
        "      motion: bare_motion.csv\n"
        "  helical:\n    series:\n      force: {file: hel_force.csv, columns: {cl: CL, cd: CD}}\n"
        "      span: {file: hel_span.csv, by: node}\n")
    rows = "\n".join(f"{t},{t * 2},{1 + t}" for t in T)       # CL = 2t, CD = 1 + t
    (folder / "bare_force.csv").write_text("time,CL,CD\n" + rows + "\n")
    rows = "\n".join(f"{t},{-t},{1}" for t in T)               # CL = -t, CD = 1
    (folder / "hel_force.csv").write_text("time,CL,CD\n" + rows + "\n")
    rows = "\n".join(f"{t},{t * t}" for t in T)                # y = t^2
    (folder / "bare_motion.csv").write_text("time,y\n" + rows + "\n")
    (folder / "hel_span.csv").write_text("time,node,y\n0,1,0\n0,2,0\n")
    return folder
