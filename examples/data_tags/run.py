"""Two cases brought into one project as tags, both with a wall zone called ``cyl``.

Usage: python run.py [DIR]   (default ./data_tags_example)

Needs no data: cylinder_case.py (examples/flow_panels) writes two generated cases under
DIR/cases/. Then, from the shell commands:

1. ``project init --import plt:... --tag smooth``: the project's folders, and the first
   case linked as data/smooth/plt with its measured domain.yml.
2. ``data import plt --path ... --tag grooved``: the second case, its own body ``cyl``.
3. The units filled in (as you would by hand), ``data check``, ``data list``, ``data info``.
4. ``data rename grooved helical``, then ``data remove helical`` (the case stays).
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


def main(folder: Path) -> None:
    folder = folder.resolve()
    case.write_case(folder / "cases" / "smooth", project=False)
    case.write_case(folder / "cases" / "grooved", steps=2, project=False)
    film = folder / "film"
    film.parent.mkdir(parents=True, exist_ok=True)
    flowreel(f"project init -o {film} --import plt:{folder / 'cases/smooth/case'} --tag smooth",
             folder)
    flowreel(f"data import plt --path {folder / 'cases/grooved/case'} --tag grooved", film)
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
