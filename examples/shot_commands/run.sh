#!/bin/sh
# The shot commands on a shot that needs no data (see shots/cylinder.yml).
# Usage: sh run.sh [DIR]   (default ./shot_commands_example). Frames go to DIR/frames/.
# Run it twice: the second render skips every frame.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
DIR=${1:-shot_commands_example}
FLOWREEL=${FLOWREEL:-flowreel}
mkdir -p "$DIR"
cd "$DIR"
$FLOWREEL project init --force >/dev/null    # a project
$FLOWREEL data import geometry --name grooved_cylinder --tag cylinder >/dev/null   # a body made in code
cp "$HERE/shot.yml" shots/cylinder.yml
cp "$HERE/cameras.yml" cameras.yml           # the views the shot uses
$FLOWREEL shot memory shots/cylinder.yml
$FLOWREEL shot preview shots/cylinder.yml --every 6
$FLOWREEL shot render shots/cylinder.yml -j 4
$FLOWREEL shot template wake --layers body,slice,iso > wake_template.yml
echo "wrote wake_template.yml"
