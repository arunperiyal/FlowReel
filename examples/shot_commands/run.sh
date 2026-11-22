#!/bin/sh
# The shot commands on a shot that needs no data (see shot.yml).
# Usage: sh run.sh [DIR]   (default ./shot_commands_example). Frames go to DIR/frames/.
# Run it twice: the second render skips every frame.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
DIR=${1:-shot_commands_example}
FLOWREEL=${FLOWREEL:-flowreel}
mkdir -p "$DIR"
cp "$HERE/shot.yml" "$HERE/cameras.yml" "$DIR/"
cd "$DIR"
$FLOWREEL project init --force >/dev/null    # a project; cameras.yml is kept
$FLOWREEL shot memory shot.yml
$FLOWREEL shot preview shot.yml --every 6
$FLOWREEL shot render shot.yml -j 4
$FLOWREEL shot template wake --layers body,slice,iso > wake_template.yml
echo "wrote wake_template.yml"
