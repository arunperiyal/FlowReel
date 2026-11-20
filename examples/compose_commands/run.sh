#!/bin/sh
# The compose commands on generated histories (the panels example's data).
# Usage: sh run.sh [DIR]   (default ./compose_example). Run it twice: the second time
# every frame is skipped.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
DIR=${1:-compose_example}
FLOWREEL=${FLOWREEL:-flowreel}
PYTHON=${PYTHON:-python}
$PYTHON - "$HERE/../panels" "$DIR" <<'PY'
import shutil, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import run                                   # examples/panels/run.py
folder = Path(sys.argv[2])
folder.mkdir(parents=True, exist_ok=True)
for name in run.FILES:
    shutil.copy(run.HERE / name, folder / name)
run.write_data(folder / "data")
PY
cd "$DIR"
$FLOWREEL compose panel compare.yml -j 2
$FLOWREEL compose layout rate_board.yml
$FLOWREEL compose layout rate_board.yml --scale 0.5 --frames 0:15:5
