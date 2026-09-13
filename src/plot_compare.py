#!/usr/bin/env python3
"""
Plot how many bees each method sees on the landing board over time, against
the Mendeley ground truth. One PNG per video.
"""
import argparse
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from beecount import load_zone  # noqa: E402
from evaluate import load_gt  # noqa: E402


def per_second(counts_by_frame, fps, n_s):
    out = np.zeros(n_s)
    hit = np.zeros(n_s)
    for fid, c in counts_by_frame.items():
        s = int((fid - 1) / fps)
        if 0 <= s < n_s:
            out[s] += c
            hit[s] += 1
    return np.divide(out, np.maximum(hit, 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", required=True)
    ap.add_argument("--zone", required=True)
    ap.add_argument("--yolo", required=True)
    ap.add_argument("--motion", default=None)
    ap.add_argument("--title", default="")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--fps", type=float, default=50.0)
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--height", type=int, default=540)
    args = ap.parse_args()

    W, H = args.width, args.height
    zone = load_zone(args.zone, W, H)
    strict = np.zeros((H, W), np.uint8)
    cv2.fillPoly(strict, [zone.astype(np.int32)], 255)

    def count_npz(path):
        d = np.load(path)
        out = {}
        for k in d.files:
            n = 0
            for b in d[k]:
                cx, cy = int(b[0] + b[2] / 2), int(b[1] + b[3] / 2)
                if 0 <= cx < W and 0 <= cy < H and strict[cy, cx]:
                    n += 1
            out[int(k)] = n
        return out

    gt_frames, _ = load_gt(args.gt, W, H)
    gt_counts = {k: len(v) for k, v in gt_frames.items()}
    n_s = int(max(gt_counts) / args.fps) + 1

    series = [("verdad del dataset", per_second(gt_counts, args.fps, n_s), "#222222", 2.2)]
    series.append(("deteccion YOLO", per_second(count_npz(args.yolo), args.fps, n_s), "#1f77b4", 1.8))
    if args.motion:
        series.append(("solo movimiento", per_second(count_npz(args.motion), args.fps, n_s),
                       "#d62728", 1.4))

    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=140)
    x = np.arange(n_s)
    for name, y, c, lw in series:
        ax.plot(x, y, label=name, color=c, linewidth=lw, alpha=0.9)
    ax.set_xlabel("segundos de video")
    ax.set_ylabel("abejas en la tabla de vuelo")
    ax.set_title(args.title or Path(args.yolo).stem)
    ax.grid(alpha=0.25)
    ax.legend(loc="upper left", framealpha=0.9)
    ax.set_xlim(0, n_s - 1)
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out)

    print(f"{args.out}")
    for name, y, _, _ in series:
        print(f"  media {name:22s}: {y.mean():5.1f} abejas/frame")


if __name__ == "__main__":
    main()
