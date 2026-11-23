#!/bin/sh
# The camera commands on a shot that needs no data (see shot.yml).
# Usage: sh run.sh [DIR]   (default ./camera_commands_example). Needs off-screen rendering.
# 'camera edit' opens a window, so it is shown last and only printed, not run.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
DIR=${1:-camera_commands_example}
FLOWREEL=${FLOWREEL:-flowreel}
mkdir -p "$DIR"
cp "$HERE/shot.yml" "$HERE/trace.py" "$DIR/"
cd "$DIR"
$FLOWREEL project init --force >/dev/null                   # the folder becomes a project
rm -f cameras.yml cameras.yml.bak
$FLOWREEL camera import trace.py wide -c cameras.yml          # a view from ParaView
$FLOWREEL camera orbit turn --shot shot.yml --station 6 --axis y --radius 6 --frames 48 \
    --azimuth 30 --span 120 --elevation 15 30                   # round the middle groove
$FLOWREEL camera path intro --keys 0:wide:hold 12:wide 48:turn_00 -c cameras.yml
$FLOWREEL camera project --track turn --points 6,0,0 6,0.5,0 --frames 0:47:23 -c cameras.yml
$FLOWREEL camera preview turn shot.yml --every 12 --scale 0.25
$FLOWREEL shot render shot.yml --frames 0,47 --save-vtp turn_vtp
echo "then, where there is a display: $FLOWREEL camera edit shot.yml --track mine"
echo "  or, with the surfaces copied: $FLOWREEL camera edit --vtp turn_vtp --track mine --frames 48 -c cameras.yml"
