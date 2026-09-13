#!/usr/bin/env python3
"""
Beehaviour PoC: motion-based bee detection, tracking and in/out counting
at the hive entrance. No trained model required.

Pipeline
  1. Downscale frame.
  2. Background subtraction (MOG2, shadows suppressed) -> moving blobs.
  3. Blob filtering by relative size (auto-calibrated to the scene).
  4. Tracking: Hungarian assignment on centroid distance, constant-velocity
     prediction, max age / min hits.
  5. Counting: a virtual line at the entrance slot. Crossing upward = IN,
     downward = OUT (hysteresis band to avoid jitter double counts).
  6. Intruder candidate: blob much larger than the median bee blob that
     persists for several frames.
  7. Output: annotated video + per-second CSV.
"""
import argparse
import csv
import math
import sys
from collections import deque
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment


# ----------------------------------------------------------------- tracking
class Track:
    _next_id = 1

    def __init__(self, cx, cy, box, area):
        self.id = Track._next_id
        Track._next_id += 1
        self.cx, self.cy = float(cx), float(cy)
        self.vx = self.vy = 0.0
        self.box = box
        self.area = area
        self.hits = 1
        self.age = 0          # frames since last matched
        self.trail = deque(maxlen=25)
        self.trail.append((int(cx), int(cy)))
        self.counted = False
        self.side = None      # 'above' / 'slot' / 'below' relative to the entrance line
        self.origin = None    # side where the track was first confirmed
        self.start_cy = float(cy)
        self.last_cx, self.last_cy = float(cx), float(cy)   # last *observed* position
        self.intruder_flagged = False
        self.big_frames = 0   # consecutive frames flagged as large blob

    def predict(self):
        return self.cx + self.vx, self.cy + self.vy

    def update(self, cx, cy, box, area):
        alpha = 0.6
        nvx, nvy = cx - self.cx, cy - self.cy
        self.vx = alpha * nvx + (1 - alpha) * self.vx
        self.vy = alpha * nvy + (1 - alpha) * self.vy
        self.cx, self.cy = float(cx), float(cy)
        self.last_cx, self.last_cy = float(cx), float(cy)
        self.box = box
        self.area = area
        self.hits += 1
        self.age = 0
        self.trail.append((int(cx), int(cy)))


class Tracker:
    def __init__(self, max_dist, max_age=8, min_hits=3):
        self.tracks = []
        self.max_dist = max_dist
        self.max_age = max_age
        self.min_hits = min_hits

    def step(self, dets):
        """dets: list of (cx, cy, box, area). Returns confirmed tracks."""
        if self.tracks and dets:
            preds = np.array([t.predict() for t in self.tracks])
            pts = np.array([[d[0], d[1]] for d in dets])
            cost = np.linalg.norm(preds[:, None, :] - pts[None, :, :], axis=2)
            rows, cols = linear_sum_assignment(cost)
            matched_t, matched_d = set(), set()
            for r, c in zip(rows, cols):
                if cost[r, c] <= self.max_dist:
                    self.tracks[r].update(*dets[c])
                    matched_t.add(r)
                    matched_d.add(c)
            for i, t in enumerate(self.tracks):
                if i not in matched_t:
                    t.age += 1
                    # coast on prediction so trail stays coherent
                    t.cx += t.vx * 0.5
                    t.cy += t.vy * 0.5
            for j, d in enumerate(dets):
                if j not in matched_d:
                    self.tracks.append(Track(*d))
        elif dets:
            self.tracks = [Track(*d) for d in dets]
        else:
            for t in self.tracks:
                t.age += 1
        lost = [t for t in self.tracks if t.age > self.max_age and t.hits >= self.min_hits]
        self.tracks = [t for t in self.tracks if t.age <= self.max_age]
        return [t for t in self.tracks if t.hits >= self.min_hits and t.age == 0], lost


# ---------------------------------------------------------------- detection
def detect_blobs(fgmask, min_area, max_area, roi_mask=None, max_aspect=3.5):
    fg = cv2.threshold(fgmask, 200, 255, cv2.THRESH_BINARY)[1]  # drop shadows (127)
    if roi_mask is not None:
        fg = cv2.bitwise_and(fg, roi_mask)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, k, iterations=1)
    k2 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, k2, iterations=2)
    n, _, stats, cents = cv2.connectedComponentsWithStats(fg, connectivity=8)
    dets = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < min_area or area > max_area:
            continue
        if max(w, h) / max(1, min(w, h)) > max_aspect:   # grass blades, wires
            continue
        if area / float(w * h) < 0.25:                   # sparse / fragmented blobs
            continue
        dets.append((cents[i][0], cents[i][1], (x, y, w, h), int(area)))
    return dets, fg


# ------------------------------------------------------------------ drawing
def put_label(img, text, org, scale=0.5, color=(255, 255, 255), bg=(0, 0, 0)):
    (tw, th), base = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
    x, y = org
    cv2.rectangle(img, (x, y - th - base), (x + tw + 4, y + base), bg, -1)
    cv2.putText(img, text, (x + 2, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)


def draw_panel(img, lines, x=10, y=10, scale=0.7):
    pad = 8
    (tw, th), _ = cv2.getTextSize("Xg", cv2.FONT_HERSHEY_SIMPLEX, scale, 2)
    w = max(cv2.getTextSize(s, cv2.FONT_HERSHEY_SIMPLEX, scale, 2)[0][0] for s in lines) + 2 * pad
    h = len(lines) * (th + 10) + pad
    overlay = img.copy()
    cv2.rectangle(overlay, (x, y), (x + w, y + h), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.6, img, 0.4, 0, img)
    for i, s in enumerate(lines):
        cv2.putText(img, s, (x + pad, y + pad + (i + 1) * (th + 10) - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 2, cv2.LINE_AA)


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("-o", "--out", default=None, help="annotated output video (.mp4)")
    ap.add_argument("--csv", default=None, help="per-second stats CSV")
    ap.add_argument("--width", type=int, default=960, help="processing width")
    ap.add_argument("--line", type=float, default=0.43,
                    help="entrance line as fraction of frame height (0=top). Above the line = inside the hive.")
    ap.add_argument("--band", type=float, default=0.035, help="half-height of the slot zone around the line (fraction of height)")
    ap.add_argument("--roi-above", type=float, default=0.10, help="region of interest: fraction of height above the line")
    ap.add_argument("--roi-below", type=float, default=0.30, help="region of interest: fraction of height below the line")
    ap.add_argument("--skip", type=int, default=1, help="process every Nth frame")
    ap.add_argument("--max-seconds", type=float, default=None)
    ap.add_argument("--intruder-ratio", type=float, default=4.0,
                    help="blob area / median bee area above which a blob is an intruder candidate")
    ap.add_argument("--show-mask", action="store_true", help="picture-in-picture of the foreground mask")
    ap.add_argument("--dets-npz", default=None, help="dump per-frame detections for evaluation")
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        sys.exit(f"cannot open {args.video}")
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    W0, H0 = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    scale = args.width / W0
    W, H = args.width, int(round(H0 * scale))
    fps = src_fps / args.skip

    # size priors relative to frame (bee at 30 cm ~ 1.5-3 % of width)
    min_area = int((W * 0.012) ** 2)
    max_area = int((W * 0.12) ** 2)
    max_dist = W * 0.045

    line_y = int(H * args.line)
    band = int(H * args.band)
    roi_top = max(0, int(line_y - H * args.roi_above))
    roi_bot = min(H, int(line_y + H * args.roi_below))
    roi_mask = np.zeros((H, W), np.uint8)
    roi_mask[roi_top:roi_bot, :] = 255

    bg = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=24, detectShadows=True)
    bg.setShadowThreshold(0.6)
    bg_lr = 0.004   # slow learning: a landed bee stays foreground for a few seconds
    tracker = Tracker(max_dist=max_dist, max_age=int(fps * 0.8), min_hits=3)

    writer = None
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(args.out, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))

    csv_rows = []
    dets_dump = {}
    n_in = n_out = 0
    intruder_events = 0
    area_hist = deque(maxlen=2000)
    sec_moving = []
    frame_idx = 0
    processed = 0
    events = []  # (time_s, kind, track_id)

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame_idx += 1
        if (frame_idx - 1) % args.skip:
            continue
        t = frame_idx / src_fps
        if args.max_seconds and t > args.max_seconds:
            break
        processed += 1

        small = cv2.resize(frame, (W, H), interpolation=cv2.INTER_AREA)
        blur = cv2.GaussianBlur(small, (5, 5), 0)
        warm = processed < int(fps * 2.0)
        fgmask = bg.apply(blur, learningRate=(-1 if warm else bg_lr))
        if warm:  # let the background model warm up
            if writer:
                writer.write(small)
            continue

        dets, fg = detect_blobs(fgmask, min_area, max_area, roi_mask)
        for d in dets:
            area_hist.append(d[3])
        median_area = float(np.median(area_hist)) if area_hist else min_area * 3

        if args.dets_npz is not None:
            dets_dump[str(frame_idx)] = np.array(
                [[d[2][0], d[2][1], d[2][2], d[2][3]] for d in dets], dtype=np.float32).reshape(-1, 4)
        confirmed, lost = tracker.step(dets)
        sec_moving.append(len(confirmed))

        # ---- counting & intruder logic
        def side_of(y):
            if y < line_y - band:
                return "above"
            if y > line_y + band:
                return "below"
            return "slot"

        def count(kind, tr, rule=""):
            nonlocal n_in, n_out
            if tr.counted:
                return
            tr.counted = True
            if kind == "IN":
                n_in += 1
            else:
                n_out += 1
            events.append((t, kind, tr.id, rule, int(tr.start_cy), int(tr.last_cy), tr.hits))

        for tr in confirmed:
            side = side_of(tr.cy)
            if tr.origin is None:
                tr.origin = side
            # rule A: explicit crossing of the line
            if tr.side == "below" and side == "above":
                count("IN", tr, "A")
            elif tr.side == "above" and side == "below":
                count("OUT", tr, "A")
            # rule B: born in the slot (came out of the hive) and now walking away
            elif tr.origin == "slot" and side == "below" and tr.hits >= 6 and tr.cy - tr.start_cy > 2 * band:
                count("OUT", tr, "B")
            tr.side = side

            if tr.area > args.intruder_ratio * median_area:
                tr.big_frames += 1
                if tr.big_frames == int(fps * 1.0) and not tr.intruder_flagged:
                    tr.intruder_flagged = True
                    intruder_events += 1
                    events.append((t, "INTRUDER?", tr.id, "", 0, 0, 0))
            else:
                tr.big_frames = 0

        # rule C: track from below that vanished inside the slot zone -> went in
        for tr in lost:
            if (not tr.counted and tr.origin == "below" and tr.hits >= 6
                    and tr.start_cy > line_y + 2 * band            # started clearly outside
                    and side_of(tr.last_cy) == "slot"               # last seen at the slot
                    and tr.start_cy - tr.last_cy > 2 * band         # net movement towards the hive
                    and tr.vy <= 0.5):                              # was not walking away
                count("IN", tr, "C")

        # ---- per-second stats
        if len(sec_moving) >= int(fps):
            csv_rows.append({
                "t_s": round(t, 1),
                "moving_bees_avg": round(float(np.mean(sec_moving)), 2),
                "in_total": n_in, "out_total": n_out,
                "intruder_events": intruder_events,
                "median_bee_area_px": round(median_area, 1),
            })
            sec_moving = []

        # ---- drawing
        if writer:
            vis = small
            cv2.line(vis, (0, line_y), (W, line_y), (255, 255, 255), 2)
            cv2.line(vis, (0, line_y - band), (W, line_y - band), (200, 200, 200), 1)
            cv2.line(vis, (0, line_y + band), (W, line_y + band), (200, 200, 200), 1)
            cv2.rectangle(vis, (0, roi_top), (W - 1, roi_bot), (90, 90, 90), 1)
            put_label(vis, "HIVE (in)", (W - 110, line_y - 10), 0.5)
            put_label(vis, "OUTSIDE", (W - 110, line_y + 22), 0.5)
            for tr in confirmed:
                x, y, w, h = tr.box
                big = tr.big_frames >= int(fps * 1.0)
                color = (0, 0, 255) if big else ((0, 200, 255) if tr.counted else (255, 120, 0))
                cv2.rectangle(vis, (x, y), (x + w, y + h), color, 2)
                put_label(vis, ("INTRUDER? " if big else "ID ") + str(tr.id), (x, max(12, y - 4)), 0.45, bg=color)
                pts = list(tr.trail)
                for i in range(1, len(pts)):
                    if math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]) <= max_dist:
                        cv2.line(vis, pts[i - 1], pts[i], color, 1)
            recent = [e for e in events if t - e[0] < 1.5]
            for i, e in enumerate(recent[-3:]):
                put_label(vis, f"{e[1]} #{e[2]}", (W // 2 - 40, 30 + 22 * i), 0.6,
                          bg=(0, 140, 0) if e[1] == "IN" else ((0, 0, 200) if e[1].startswith("INTR") else (0, 90, 200)))
            draw_panel(vis, [
                f"IN: {n_in}   OUT: {n_out}",
                f"moving now: {len(confirmed)}",
                f"intruder events: {intruder_events}",
                f"t = {t:6.1f}s",
            ])
            if args.show_mask:
                pip = cv2.cvtColor(cv2.resize(fg, (W // 4, H // 4)), cv2.COLOR_GRAY2BGR)
                vis[H - H // 4 - 10:H - 10, 10:10 + W // 4] = pip
            writer.write(vis)

        if processed % int(fps * 10) == 0:
            print(f"t={t:6.1f}s  in={n_in} out={n_out} moving={len(confirmed)} "
                  f"median_area={median_area:.0f}px  intruders={intruder_events}", flush=True)

    cap.release()
    if writer:
        writer.release()
    if args.dets_npz:
        Path(args.dets_npz).parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(args.dets_npz, **dets_dump)
    if args.csv:
        Path(args.csv).parent.mkdir(parents=True, exist_ok=True)
        with open(args.csv, "w", newline="") as f:
            wtr = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
            wtr.writeheader()
            wtr.writerows(csv_rows)

    print("\n=== summary ===")
    print(f"video: {args.video}  ({W}x{H} @ {fps:.1f} fps processed, {processed} frames)")
    print(f"IN: {n_in}   OUT: {n_out}   net: {n_in - n_out:+d}")
    print(f"intruder candidates: {intruder_events}")
    if csv_rows:
        mv = [r['moving_bees_avg'] for r in csv_rows]
        print(f"moving bees per frame: mean {np.mean(mv):.1f}, max {np.max(mv):.1f}")
    from collections import Counter
    print("by rule:", dict(Counter((e[1], e[3]) for e in events)))
    for e in events[:40]:
        print(f"  {e[0]:6.1f}s  {e[1]:9s} track {e[2]:5d} rule {e[3]} y {e[4]}->{e[5]} hits {e[6]}")
    if len(events) > 40:
        print(f"  ... {len(events) - 40} more events")


if __name__ == "__main__":
    main()
