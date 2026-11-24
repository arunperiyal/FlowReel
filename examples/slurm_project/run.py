"""Render a generated shot through Slurm, on any machine: fake_sbatch.py stands in for
sbatch and runs each job here.

Usage: python run.py [DIR]   (default ./slurm_project_example)

1. `flowreel shot render wake.yml --submit --cpus 2`: the shot is not measured yet, so
   the first job measures one frame and then submits the render, a job array of two
   tasks, which draws all 24 frames.
2. The same with --force while only task 0 runs (FAKE_SBATCH_TASKS=0): a render cut
   short. Task 1's frames are deleted, as if never drawn.
3. `--submit --missing`: one task, for the frames left; nothing else is redrawn.
4. `flowreel jobs status` lists the jobs.

On a cluster the same commands, without the fake, submit real jobs (docs/guide/making/slurm.md).
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHOT = """name: wake
source: geometry:grooved_cylinder
time: {frozen: 0, frames: 24}
camera: {view: main}
size: [160, 90]
antialias: none
layers:
  - {type: outline, width: 2}
  - {type: geometry, body: grooved_cylinder, colour: "#e8b04a"}
"""
CAMERAS = "views:\n  - {name: main, position: [0, -30, 3], focal: [0, 0, 3], up: [0, 0, 1]}\n"


def flowreel(folder: Path, *args: str, env: dict) -> str:
    done = subprocess.run([sys.executable, "-m", "flowreel", *args], cwd=folder, env=env,
                          capture_output=True, text=True)
    if done.returncode != 0:
        raise SystemExit(done.stderr)
    return done.stdout


def main(folder: Path) -> None:
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    (folder / "wake.yml").write_text(SHOT)
    (folder / "cameras.yml").write_text(CAMERAS)
    (folder / "flowreel.yml").write_text("")             # a project (docs/guide/projects/project.md)
    sbatch = folder / "bin" / "sbatch"
    sbatch.parent.mkdir()
    sbatch.write_text(f"#!/bin/bash\nexec {sys.executable} {HERE / 'fake_sbatch.py'} \"$@\"\n")
    sbatch.chmod(0o755)
    quiet = folder / "bin" / "squeue"                    # the fake's jobs end at once
    quiet.write_text("#!/bin/bash\n")
    quiet.chmod(0o755)
    env = {**os.environ, "FLOWREEL_SBATCH": str(sbatch), "FLOWREEL_SQUEUE": str(quiet),
           "FLOWREEL_SACCT": str(quiet), "FLOWREEL_CLUSTER": "airavata",
           "FAKE_SBATCH_STATE": str(folder / "bin" / "state.json")}
    frames = folder / "frames" / "wake"

    print(flowreel(folder, "shot", "render", "wake.yml", "--submit", "--cpus", "2", env=env), end="")
    print(f"-> {len(list(frames.glob('frame_*.png')))} frames drawn\n")
    out = flowreel(folder, "shot", "render", "wake.yml", "--submit", "--cpus", "2", "--force",
                   env={**env, "FAKE_SBATCH_TASKS": "0"})
    print(out.splitlines()[0] + "   (only task 0 runs)")
    for f in sorted(frames.glob("frame_*.png"))[16:]:
        f.unlink()
    print(f"-> {len(list(frames.glob('frame_*.png')))} frames left\n")
    print(flowreel(folder, "shot", "render", "wake.yml", "--submit", "--missing", "--cpus", "2",
                   env=env), end="")
    print(f"-> {len(list(frames.glob('frame_*.png')))} frames drawn\n")
    print(flowreel(folder, "jobs", "status", env=env), end="")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("slurm_project_example"))
