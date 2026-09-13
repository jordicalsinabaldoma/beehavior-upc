#!/usr/bin/env bash
# Run the detection pipeline on the three test videos, render the dashboard
# video and evaluate against the Mendeley ground truth.
#
#   ./run_all.sh [weights]
set -euo pipefail
cd "$(dirname "$0")"

PY=.venv/bin/python
W=${1:-models/bee11n.pt}
GT="data/Labeled dataset for bee detection and direction estimation on beehive landing boards/tracking_and_behavior"
VIDEOS=(20230609b-def 20230711a-fan 20230711b-fan)

mkdir -p out
for v in "${VIDEOS[@]}"; do
  echo "=============================================================== $v"
  $PY src/beecount.py "dataset-minimal/$v.mp4" \
      --weights "$W" \
      --zone "$GT/entrance_zone_$v.txt" \
      --imgsz 640 --conf 0.40 --skip 2 \
      --render-width 1280 --panel 340 \
      -o "out/${v}_raw.mp4" \
      --csv "out/${v}.csv" \
      --events-csv "out/${v}_events.csv" \
      --dets-npz "out/${v}_dets.npz" | tee "out/${v}.log"

  ffmpeg -v error -y -i "out/${v}_raw.mp4" \
         -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p "out/${v}_beehaviour.mp4"
  rm -f "out/${v}_raw.mp4"

  IN=$(grep -oP '(?<=^IN )\d+' "out/${v}.log" | head -1)
  OUT=$(grep -oP '(?<=OUT )\d+' "out/${v}.log" | head -1)
  $PY src/evaluate.py --gt "$GT/tracks_$v.txt" --zone "$GT/entrance_zone_$v.txt" \
      --dets "out/${v}_dets.npz" --ours-in "$IN" --ours-out "$OUT" \
      | tee "out/${v}_eval.txt"

  $PY src/plot_compare.py --gt "$GT/tracks_$v.txt" --zone "$GT/entrance_zone_$v.txt" \
      --yolo "out/${v}_dets.npz" --motion "out/motion_$v.npz" \
      --title "$v" -o "out/${v}_actividad.png" || true
done
echo
echo "listo:"
ls -1 out/*_beehaviour.mp4 out/*_actividad.png
