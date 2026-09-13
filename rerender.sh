#!/usr/bin/env bash
# Re-draw the annotated videos from saved detections. No inference.
set -euo pipefail
cd "$(dirname "$0")"
# Paths. Override with environment variables if the dataset lives elsewhere:
#   DATASET=/mnt/data/bees VIDEOS_DIR=/mnt/data/bees/videos ./rerender.sh
PY=${PYTHON:-.venv/bin/python}
DATASET=${DATASET:-"data/Labeled dataset for bee detection and direction estimation on beehive landing boards"}
GT=${GT:-"$DATASET/tracking_and_behavior"}
VIDEOS_DIR=${VIDEOS_DIR:-"$GT"}
declare -A NAME=( [20230609b-def]="HIVE 01" [20230711a-fan]="HIVE 02" [20230711b-fan]="HIVE 03" )
for v in "${!NAME[@]}"; do
  echo "=== $v"
  $PY src/beecount.py "$VIDEOS_DIR/$v.mp4" \
      --from-dets "out/${v}_dets.npz" --zone "$GT/entrance_zone_$v.txt" \
      --layout strip --title "${NAME[$v]}" --no-intruder \
      -o "out/${v}_strip_raw.mp4" --csv "out/${v}.csv" --events-csv "out/${v}_events.csv" \
      | tail -6
  ffmpeg -v error -y -i "out/${v}_strip_raw.mp4" -c:v libx264 -preset medium -crf 20 \
         -pix_fmt yuv420p "out/${v}_beehaviour.mp4"
  rm -f "out/${v}_strip_raw.mp4"
done
ls -la out/*_beehaviour.mp4
