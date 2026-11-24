#!/bin/sh
# A project folder made by project init, a body brought in as a tag, a shot rendered from
# inside it, then the project looked at and cleaned.
# Usage: sh run.sh [DIR]   (default ./project_example). Needs off-screen rendering.
# The body is generated (the tag cylinder has no files); a real case would be linked into
# data/ by `data import plt` and never copied.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
DIR=${1:-project_example}
FLOWREEL=${FLOWREEL:-flowreel}
rm -rf "$DIR"
mkdir -p "$DIR"
$FLOWREEL project init -o "$DIR/film"
cd "$DIR/film"
$FLOWREEL data import geometry --name grooved_cylinder --tag cylinder   # -> data/cylinder/
cp "$HERE/shot.yml" shots/cylinder.yml
cd shots                           # any folder in the project will do
$FLOWREEL shot render cylinder.yml --frames 0:11:11 --scale 0.25   # -> ../frames/
$FLOWREEL project info
$FLOWREEL project clean --frames --dry-run
$FLOWREEL project clean
