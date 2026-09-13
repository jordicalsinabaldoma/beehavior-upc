#!/usr/bin/env python3
"""
Choose the detection confidence threshold on the VALIDATION split.

The validation images come from the same hives as training and never from the
three test videos, so the threshold is not tuned on the data we report
results on.
"""
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate import match  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True)
    ap.add_argument("--val-dir", default="data/yolo_bees/images/val")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--iou", type=float, default=0.3)
    ap.add_argument("--limit", type=int, default=120)
    args = ap.parse_args()

    from ultralytics import YOLO
    model = YOLO(args.weights)

    imgs = sorted(Path(args.val_dir).glob("*.jpg"))[:args.limit]
    grid = np.arange(0.05, 0.76, 0.05)
    stats = {c: [0, 0, 0] for c in grid}   # tp, fp, fn

    for ip in imgs:
        img = cv2.imread(str(ip))
        H, W = img.shape[:2]
        lp = Path(str(ip).replace("/images/", "/labels/")).with_suffix(".txt")
        gts = []
        for line in lp.read_text().strip().split("\n"):
            _, xc, yc, w, h = [float(v) for v in line.split()]
            gts.append(((xc - w / 2) * W, (yc - h / 2) * H, w * W, h * H))

        r = model.predict(img, conf=float(grid[0]), imgsz=args.imgsz,
                          verbose=False, max_det=300)[0]
        boxes = r.boxes.xyxy.cpu().numpy()
        confs = r.boxes.conf.cpu().numpy()
        for c in grid:
            d = [(b[0], b[1], b[2] - b[0], b[3] - b[1])
                 for b, cf in zip(boxes, confs) if cf >= c]
            tp = match(d, gts, args.iou)
            stats[c][0] += tp
            stats[c][1] += len(d) - tp
            stats[c][2] += len(gts) - tp

    print(f"{len(imgs)} imagenes de validacion, IoU>={args.iou}")
    print(f"{'conf':>6} {'prec':>7} {'recall':>7} {'F1':>7}")
    best = (0, None)
    for c in grid:
        tp, fp, fn = stats[c]
        p = tp / max(tp + fp, 1)
        r_ = tp / max(tp + fn, 1)
        f1 = 2 * p * r_ / max(p + r_, 1e-9)
        print(f"{c:6.2f} {p:7.3f} {r_:7.3f} {f1:7.3f}")
        if f1 > best[0]:
            best = (f1, c)
    print(f"\nmejor conf = {best[1]:.2f}  (F1 {best[0]:.3f})")


if __name__ == "__main__":
    main()
