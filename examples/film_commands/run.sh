#!/bin/sh
# The film commands on the film_build example's generated frames and tone.
# Usage: sh run.sh [DIR]   (default ./film_commands_example). Needs ffmpeg only.
# Run it twice: the second build keeps every clip and only joins again.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
DIR=${1:-film_commands_example}
FLOWREEL=${FLOWREEL:-flowreel}
PYTHON=${PYTHON:-python}
$PYTHON - "$HERE/../film_build" "$DIR" <<'PY'
import shutil, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import run                                   # examples/film_build/run.py
folder = Path(sys.argv[2])
folder.mkdir(parents=True, exist_ok=True)
for name in ("film.yml", "card.yml"):
    shutil.copy(run.HERE / name, folder / name)
run.wake(folder / "frames" / "wake")
run.tone(folder / "tone.wav")
PY
cd "$DIR"
$FLOWREEL project init --force >/dev/null              # a project; film.yml is kept
$FLOWREEL film template wake -o template.yml --force   # a film file to start from
$FLOWREEL film lengths                                 # planned; nothing built yet
$FLOWREEL film build --preview 180
$FLOWREEL film lengths                                 # now measured too
$FLOWREEL film check --at caption --width 320
$FLOWREEL film srt
$FLOWREEL film chapters
