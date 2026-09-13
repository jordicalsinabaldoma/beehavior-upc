#!/usr/bin/env python3
"""
Build a demo clip with a SYNTHETIC intruder in front of the hive entrance.

The Mendeley dataset contains only bees, so there is no real hornet footage to
test the "something that is not a bee" alert with. This composites a dark,
slow, bee-sized-times-three object that hovers over the landing board, which
is how a Vespa velutina behaves when it hunts at the entrance.

It is a stand-in for a demo, not evidence that real hornets are detected.
"""
import argparse
from pathlib import Path

import cv2
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--start", type=float, default=20.0, help="seconds into the clip")
    ap.add_argument("--duration", type=float, default=40.0)
    ap.add_argument("--enter-at", type=float, default=12.0,
                    help="seconds into the OUTPUT clip when the intruder shows up")
    ap.add_argument("--leave-at", type=float, default=30.0)
    ap.add_argument("--y", type=float, default=0.52, help="hover height, fraction of frame")
    ap.add_argument("--size", type=float, default=0.055, help="body length, fraction of width")
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 50.0
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(args.start * fps))

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    wr = cv2.VideoWriter(args.out, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))

    n = int(args.duration * fps)
    L = int(args.size * W)          # body length
    rng = np.random.default_rng(0)
    drawn = 0

    for i in range(n):
        ok, f = cap.read()
        if not ok:
            break
        t = i / fps
        if args.enter_at <= t <= args.leave_at:
            # slow hovering drift with a small jitter, the way a hornet holds station
            u = (t - args.enter_at) / max(args.leave_at - args.enter_at, 1e-6)
            cx = int(W * (0.25 + 0.5 * (0.5 - 0.5 * np.cos(2 * np.pi * u * 1.5))))
            cy = int(H * args.y + 18 * np.sin(2 * np.pi * u * 6))
            cx += int(rng.normal(0, 2))
            cy += int(rng.normal(0, 2))
            ang = 12 * np.sin(2 * np.pi * u * 3)

            ov = f.copy()
            cv2.ellipse(ov, (cx, cy), (L // 2, L // 4), ang, 0, 360, (18, 20, 26), -1)
            cv2.ellipse(ov, (cx + int(L * 0.32 * np.cos(np.radians(ang))),
                             cy + int(L * 0.32 * np.sin(np.radians(ang)))),
                        (L // 6, L // 6), ang, 0, 360, (10, 12, 16), -1)
            # blurred wings
            for s in (-1, 1):
                cv2.ellipse(ov, (cx, cy + s * L // 5), (L // 3, L // 9), ang, 0, 360,
                            (120, 120, 120), -1)
            f = cv2.addWeighted(ov, 0.92, f, 0.08, 0)
            drawn += 1
        wr.write(f)

    cap.release()
    wr.release()
    print(f"{args.out}: {i + 1} frames, intruder drawn on {drawn} of them "
          f"({args.enter_at:.0f}s-{args.leave_at:.0f}s), body {L}px")


if __name__ == "__main__":
    main()
