#!/bin/sh
# The shot commands on a shot that needs no data. Run from anywhere; frames go to
# ./frames/. Run it twice: the second render skips every frame.
set -e
HERE=$(dirname "$0")
flowreel shot memory "$HERE/shot.yml"
flowreel shot preview "$HERE/shot.yml" --every 6
flowreel shot render "$HERE/shot.yml" -j 4
flowreel shot template wake --layers body,slice,iso > wake_template.yml
echo "wrote wake_template.yml"
