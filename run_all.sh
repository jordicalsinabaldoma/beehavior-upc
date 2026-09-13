#!/usr/bin/env bash
# Run the detection pipeline on the three test videos and evaluate it
# against the Mendeley ground truth.
#
#   ./run_all.sh [weights]
set -euo pipefail
cd "$(dirname "$0")"

PY=.venv/bin/python
W=${1:-runs/detect/runs/bee11n/weights/best.pt}
GT="data/Labeled dataset for bee detection and direction estimation on beehive landing boards/tracking_and_behavior"
VIDEOS=(20230609b-def 20230711a-fan 20230711b-fan)

mkdir -p out
for v in "${VIDEOS[@]}"; do
  echo "=============================================================== $v"
  $PY src/beecount.py "dataset-minimal/$v.mp4" \
      --weights "$W" \
      --zone "$GT/entrance_zone_$v.txt" \
      --imgsz 640 --conf 0.25 --skip 2 \
      -o "out/${v}_yolo_raw.mp4" \
      --csv "out/${v}_yolo.csv" \
      --events-csv "out/${v}_yolo_events.csv" \
      --dets-npz "out/${v}_yolo_dets.npz" | tee "out/${v}_yolo.log"

  # re-encode so the clip plays in a browser or on a phone
  ffmpeg -v error -y -i "out/${v}_yolo_raw.mp4" \
         -c:v libx264 -preset fast -crf 22 -pix_fmt yuv420p "out/${v}_yolo.mp4"
  rm -f "out/${v}_yolo_raw.mp4"

  IN=$(grep -oP '(?<=^IN )\d+' "out/${v}_yolo.log" | head -1)
  OUT=$(grep -oP '(?<=OUT )\d+' "out/${v}_yolo.log" | head -1)
  $PY src/evaluate.py --gt "$GT/tracks_$v.txt" --zone "$GT/entrance_zone_$v.txt" \
      --dets "out/${v}_yolo_dets.npz" --ours-in "$IN" --ours-out "$OUT" \
      | tee "out/${v}_eval.txt"
done
echo "listo. videos anotados en out/*_yolo.mp4"
