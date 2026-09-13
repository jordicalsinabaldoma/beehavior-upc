#!/usr/bin/env python3
"""
Evaluate detection and counting against the Mendeley ground truth.

Ground truth files (tracking_and_behavior/tracks_<video>.txt) are MOT-style:
    frame-id, track-id, bb-left, bb-top, bb-width, bb-height   (normalised)
and cover only bees inside the landing-board polygon.

Two things are measured:

1. Detection quality. Per frame, greedy IoU matching between our detections
   and the ground-truth boxes -> precision, recall, F1. Only ground-truth
   frames that we actually processed are used.

2. Counting. The ground truth has no in/out labels, so the SAME geometric
   rules are applied to the ground-truth tracks and to ours, and the two
   totals are compared. This measures detection and tracking error, not the
   counting rule itself.
"""
import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from beecount import Entrance, load_zone, iou  # noqa: E402


def load_gt(path, W, H):
    """-> {frame_id: [(x, y, w, h), ...]}, {track_id: [(frame, cx, cy), ...]}"""
    a = np.loadtxt(path, delimiter=",")
    by_frame = defaultdict(list)
    by_track = defaultdict(list)
    for fid, tid, x, y, w, h in a:
        box = (x * W, y * H, w * W, h * H)
        by_frame[int(fid)].append(box)
        by_track[int(tid)].append((int(fid), box[0] + box[2] / 2, box[1] + box[3] / 2))
    for t in by_track.values():
        t.sort()
    return by_frame, by_track


def match(dets, gts, thr=0.3):
    """Greedy IoU matching -> number of true positives."""
    if not dets or not gts:
        return 0
    m = np.array([[iou(d, g) for g in gts] for d in dets])
    tp = 0
    while True:
        i, j = np.unravel_index(np.argmax(m), m.shape)
        if m[i, j] < thr:
            break
        tp += 1
        m[i, :] = -1
        m[:, j] = -1
    return tp


def count_tracks(by_track, entrance, band, min_len=5):
    """Apply the pipeline's rules to whole trajectories."""
    n_in = n_out = 0
    for pts in by_track.values():
        if len(pts) < min_len:
            continue
        ys = [p[2] for p in pts]
        xs = [p[1] for p in pts]
        sides = [entrance.side(x, y) for x, y in zip(xs, ys)]
        counted = None
        for k in range(1, len(sides)):
            if sides[k - 1] == "below" and sides[k] == "above":
                counted = "IN"
                break
            if sides[k - 1] == "above" and sides[k] == "below":
                counted = "OUT"
                break
        if counted is None:
            if sides[0] in ("slot", "above") and sides[-1] == "below" and ys[-1] - ys[0] > 2 * band:
                counted = "OUT"
            elif sides[0] == "below" and sides[-1] in ("slot", "above") and ys[0] - ys[-1] > 2 * band:
                counted = "IN"
        if counted == "IN":
            n_in += 1
        elif counted == "OUT":
            n_out += 1
    return n_in, n_out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", required=True)
    ap.add_argument("--zone", required=True)
    ap.add_argument("--dets", required=True, help=".npz written by beecount.py --dets-npz")
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--height", type=int, default=540)
    ap.add_argument("--band", type=float, default=0.025)
    ap.add_argument("--iou", type=float, default=0.3)
    ap.add_argument("--ours-in", type=int, default=None)
    ap.add_argument("--ours-out", type=int, default=None)
    args = ap.parse_args()

    W, H = args.width, args.height
    band = H * args.band
    zone = load_zone(args.zone, W, H)
    entrance = Entrance.from_zone(zone, band)

    gt_frames, gt_tracks = load_gt(args.gt, W, H)
    dets = np.load(args.dets)

    # ground truth only covers the landing-board polygon, so detections
    # outside it must not be scored as false positives
    strict = np.zeros((H, W), np.uint8)
    cv2.fillPoly(strict, [zone.astype(np.int32)], 255)

    def inside(b):
        cx, cy = int(b[0] + b[2] / 2), int(b[1] + b[3] / 2)
        return 0 <= cx < W and 0 <= cy < H and strict[cy, cx] > 0

    tp = fp = fn = 0
    n_eval = 0
    for key in dets.files:
        fid = int(key)
        if fid not in gt_frames:
            continue
        d = [tuple(b) for b in dets[key] if inside(b)]
        g = gt_frames[fid]
        m = match(d, g, args.iou)
        tp += m
        fp += len(d) - m
        fn += len(g) - m
        n_eval += 1

    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)
    f1 = 2 * prec * rec / max(prec + rec, 1e-9)

    gin, gout = count_tracks(gt_tracks, entrance, band)

    print(f"frames compared : {n_eval}")
    print(f"gt boxes        : {tp + fn}")
    print(f"our detections  : {tp + fp}")
    print(f"precision {prec:.3f}   recall {rec:.3f}   F1 {f1:.3f}   (IoU>={args.iou})")
    print()
    print(f"ground-truth tracks in the zone : {len(gt_tracks)}")
    print(f"same rules on ground truth      : IN {gin}   OUT {gout}")
    if args.ours_in is not None:
        print(f"ours                            : IN {args.ours_in}   OUT {args.ours_out}")
        print(f"error                           : IN {args.ours_in - gin:+d} "
              f"({(args.ours_in - gin) / max(gin,1) * 100:+.0f}%)   "
              f"OUT {args.ours_out - gout:+d} ({(args.ours_out - gout) / max(gout,1) * 100:+.0f}%)")


if __name__ == "__main__":
    main()
