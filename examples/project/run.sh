#!/bin/sh
# A project folder made by project init, used from inside it, then looked at and cleaned.
# Usage: sh run.sh [DIR]   (default ./project_example). Needs off-screen rendering.
# The "data" is a generated folder, linked into data/ and never copied.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
DIR=${1:-project_example}
FLOWREEL=${FLOWREEL:-flowreel}
rm -rf "$DIR"
mkdir -p "$DIR/case"
echo "stands in for a simulation's output" > "$DIR/case/README.txt"
$FLOWREEL project init geometry:grooved_cylinder -o "$DIR/film" --link "$DIR/case"
cp "$HERE/shot.yml" "$DIR/film/shots/cylinder.yml"
cd "$DIR/film/shots"                           # any folder in the project will do
$FLOWREEL shot render cylinder.yml --frames 0:11:11 --scale 0.25   # -> ../frames/
$FLOWREEL project info
$FLOWREEL project clean --frames --dry-run
$FLOWREEL project clean
