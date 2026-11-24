"""Two cases brought into one project as tags, both with a wall zone called ``cyl``.

Usage: python run.py [DIR]   (default ./data_tags_example)

Needs no data: cylinder_case.py (examples/flow_panels) writes two generated cases under
DIR/cases/. Then, from the shell commands:

1. ``project init --import plt:... --tag smooth``: the project's folders, and the first
   case linked as data/smooth/plt with its measured domain.yml.
2. ``data import plt --path ... --tag grooved``: the second case, its own body ``cyl``.
3. ``data import history``: generated OTHD and OISD files of the smooth case (two runs,
   the second a restart), a CSV a group, declared as the body's displacement and force.
4. The units filled in (as you would by hand), ``data check``, ``data list``, ``data info``.
5. ``data rename grooved helical``, then ``data remove helical`` (the case stays).
"""
import shlex
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "flow_panels"))
import cylinder_case as case  # noqa: E402


def flowreel(line: str, cwd: Path) -> None:
    print(f"$ flowreel {line}")
    done = subprocess.run([sys.executable, "-m", "flowreel", *shlex.split(line)], cwd=cwd,
                          capture_output=True, text=True)
    print(done.stdout + done.stderr, end="")


def write_history(case: Path) -> None:
    """OTHD and OISD files as FlexFlow writes them, three probe nodes: run 2 resumed at
    t = 0.2, so that time is written twice (the later run wins)."""
    def othd(times, shift):
        out = []
        for k, t in enumerate(times):
            out += [f"tsId {k + 1}", f"time {t}", "othId 0", "aleDisp 3 3"]
            out += [f"0 {shift + t * (1 + n)} 0" for n in range(3)]
        return "\n".join(out) + "\n"
    runs = case / "othd_files" / "archive"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / "smooth1.othd").write_text(othd([0.0, 0.5, 1.0], 0.0))
    (runs / "smooth2.othd").write_text(othd([1.0, 1.5], 0.001))
    oisd = case / "oisd_files"
    oisd.mkdir(exist_ok=True)
    (oisd / "smooth1.oisd").write_text("".join(
        f"tsId {k + 1}\ntime {t}\nosgId 0\ntotArea 3.1\ntotTrac 3 1\n{t} {0.5 * t} 0\n"
        for k, t in enumerate([0.0, 0.5, 1.0, 1.5])))


def main(folder: Path) -> None:
    folder = folder.resolve()
    case.write_case(folder / "cases" / "smooth", project=False)
    case.write_case(folder / "cases" / "grooved", steps=2, project=False)
    film = folder / "film"
    film.parent.mkdir(parents=True, exist_ok=True)
    flowreel(f"project init -o {film} --import plt:{folder / 'cases/smooth/case'} --tag smooth",
             folder)
    flowreel(f"data import plt --path {folder / 'cases/grooved/case'} --tag grooved", film)
    write_history(folder / "cases" / "smooth")
    flowreel(f"data import history --path {folder / 'cases/smooth'} --tag smooth", film)
    for tag in ("smooth", "grooved"):
        path = film / "data" / tag / "domain.yml"
        path.write_text(path.read_text().replace(
            "units:", "units: {rho: 1.0, mu: 0.001, u_inf: 1.0}\n#", 1))
    flowreel("data check", film)
    flowreel("data list", film)
    flowreel("data info grooved", film)
    flowreel("data rename grooved helical", film)
    flowreel("data remove helical", film)
    flowreel("data list", film)


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data_tags_example"))
