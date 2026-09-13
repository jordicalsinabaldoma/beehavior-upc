#!/usr/bin/env python3
"""
Beehaviour: bee detection (YOLO), tracking, in/out counting and intruder
alerting at the hive entrance.

Differences from the earlier motion-only prototype (src/beetrack.py):
  * bees are found by a trained detector, so a bee that stops walking is
    still detected and keeps its track id;
  * the entrance line comes from the landing-board polygon, so it can be
    sloped and is read from a file instead of hand-tuned;
  * an intruder is motion that the bee detector does NOT explain, instead of
    "a blob bigger than the others".
"""
import argparse
import csv
import math
import re
import sys
from collections import deque, Counter
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment


# ------------------------------------------------------------------ geometry
def load_zone(path, W, H):
    """Read `polygon = np.array([[x, y], ...])` and return pixel coords scaled to WxH.

    The dataset polygons are given in the original 1920x1080 frame.
    """
    txt = Path(path).read_text()
    nums = [int(n) for n in re.findall(r"-?\d+", txt)]
    pts = np.array(nums, dtype=float).reshape(-1, 2)
    pts[:, 0] *= W / 1920.0
    pts[:, 1] *= H / 1080.0
    return pts


class Entrance:
    """The hive-side edge of the landing board: a (possibly sloped) segment.

    Signed distance is positive below the line (outside, on the board) and
    negative above it (hive side).
    """

    def __init__(self, p0, p1, band):
        self.p0, self.p1 = np.asarray(p0, float), np.asarray(p1, float)
        self.band = band

    @classmethod
    def from_zone(cls, zone, band):
        # the two topmost polygon corners define the hive-side edge
        idx = np.argsort(zone[:, 1])[:2]
        a, b = zone[idx[0]], zone[idx[1]]
        if a[0] > b[0]:
            a, b = b, a
        return cls(a, b, band)

    @classmethod
    def horizontal(cls, W, y, band):
        return cls((0.0, y), (float(W), y), band)

    def y_at(self, x):
        x0, y0 = self.p0
        x1, y1 = self.p1
        if abs(x1 - x0) < 1e-6:
            return y0
        return y0 + (y1 - y0) * (x - x0) / (x1 - x0)

    def dist(self, x, y):
        return y - self.y_at(x)

    def side(self, x, y):
        d = self.dist(x, y)
        if d < -self.band:
            return "above"
        if d > self.band:
            return "below"
        return "slot"


# ------------------------------------------------------------------ tracking
def iou(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x0, y0 = max(ax, bx), max(ay, by)
    x1, y1 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    inter = (x1 - x0) * (y1 - y0)
    return inter / (aw * ah + bw * bh - inter)


class Track:
    _next_id = 1

    @classmethod
    def reset(cls):
        cls._next_id = 1

    def __init__(self, det, entrance):
        self.id = Track._next_id
        Track._next_id += 1
        self.box = det                      # (x, y, w, h)
        self.cx, self.cy = det[0] + det[2] / 2, det[1] + det[3] / 2
        self.vx = self.vy = 0.0
        self.hits = 1
        self.age = 0
        self.trail = deque(maxlen=40)
        self.trail.append((int(self.cx), int(self.cy)))
        self.start = (self.cx, self.cy)
        self.last_seen = (self.cx, self.cy)
        self.side = entrance.side(self.cx, self.cy)
        self.origin_side = self.side
        self.counted = None                 # 'IN' / 'OUT'

    def predict(self):
        return self.cx + self.vx, self.cy + self.vy

    def update(self, det, entrance):
        cx, cy = det[0] + det[2] / 2, det[1] + det[3] / 2
        a = 0.5
        self.vx = a * (cx - self.cx) + (1 - a) * self.vx
        self.vy = a * (cy - self.cy) + (1 - a) * self.vy
        self.cx, self.cy = cx, cy
        self.last_seen = (cx, cy)
        self.box = det
        self.hits += 1
        self.age = 0
        self.trail.append((int(cx), int(cy)))

    def coast(self):
        self.age += 1
        self.cx += self.vx * 0.6
        self.cy += self.vy * 0.6


class Tracker:
    def __init__(self, max_dist, max_age, min_hits, entrance):
        self.tracks = []
        self.max_dist = max_dist
        self.max_age = max_age
        self.min_hits = min_hits
        self.entrance = entrance

    def step(self, dets):
        if self.tracks and dets:
            pred = np.array([t.predict() for t in self.tracks])
            cent = np.array([[d[0] + d[2] / 2, d[1] + d[3] / 2] for d in dets])
            dist = np.linalg.norm(pred[:, None, :] - cent[None, :, :], axis=2)
            # prefer overlapping boxes, fall back to proximity
            ious = np.array([[iou(t.box, d) for d in dets] for t in self.tracks])
            cost = dist / self.max_dist - 0.5 * ious
            cost[dist > self.max_dist] = 1e6
            rows, cols = linear_sum_assignment(cost)
            mt, md = set(), set()
            for r, c in zip(rows, cols):
                if cost[r, c] < 1e5:
                    self.tracks[r].update(dets[c], self.entrance)
                    mt.add(r)
                    md.add(c)
            for i, t in enumerate(self.tracks):
                if i not in mt:
                    t.coast()
            for j, d in enumerate(dets):
                if j not in md:
                    self.tracks.append(Track(d, self.entrance))
        elif dets:
            self.tracks += [Track(d, self.entrance) for d in dets]
        else:
            for t in self.tracks:
                t.coast()

        lost = [t for t in self.tracks if t.age > self.max_age and t.hits >= self.min_hits]
        self.tracks = [t for t in self.tracks if t.age <= self.max_age]
        live = [t for t in self.tracks if t.hits >= self.min_hits and t.age == 0]
        return live, lost


# ----------------------------------------------------------------- detectors
class YoloDetector:
    def __init__(self, weights, conf, imgsz):
        from ultralytics import YOLO
        self.model = YOLO(weights)
        self.conf = conf
        self.imgsz = imgsz

    def __call__(self, frame):
        r = self.model.predict(frame, conf=self.conf, imgsz=self.imgsz,
                               verbose=False, max_det=300)[0]
        out = []
        for b in r.boxes.xyxy.cpu().numpy():
            x0, y0, x1, y1 = b
            out.append((float(x0), float(y0), float(x1 - x0), float(y1 - y0)))
        return out


# ------------------------------------------------------------------- drawing
def put_label(img, text, org, scale=0.45, color=(255, 255, 255), bg=(0, 0, 0)):
    (tw, th), base = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
    x, y = int(org[0]), int(org[1])
    cv2.rectangle(img, (x, y - th - base), (x + tw + 4, y + base), bg, -1)
    cv2.putText(img, text, (x + 2, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)


def draw_panel(img, lines, x=10, y=10, scale=0.7):
    pad = 8
    (_, th), _ = cv2.getTextSize("Xg", cv2.FONT_HERSHEY_SIMPLEX, scale, 2)
    w = max(cv2.getTextSize(s, cv2.FONT_HERSHEY_SIMPLEX, scale, 2)[0][0] for s in lines) + 2 * pad
    h = len(lines) * (th + 10) + pad
    ov = img.copy()
    cv2.rectangle(ov, (x, y), (x + w, y + h), (20, 20, 20), -1)
    cv2.addWeighted(ov, 0.65, img, 0.35, 0, img)
    for i, s in enumerate(lines):
        cv2.putText(img, s, (x + pad, y + pad + (i + 1) * (th + 10) - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 2, cv2.LINE_AA)


def sparkline(img, values, box, color=(0, 220, 255), vmax=None):
    x, y, w, h = box
    ov = img.copy()
    cv2.rectangle(ov, (x, y), (x + w, y + h), (20, 20, 20), -1)
    cv2.addWeighted(ov, 0.65, img, 0.35, 0, img)
    if len(values) < 2:
        return
    vmax = vmax or max(max(values), 1)
    pts = []
    for i, v in enumerate(values):
        px = x + int(i * w / (len(values) - 1))
        py = y + h - int(min(v / vmax, 1.0) * (h - 4)) - 2
        pts.append((px, py))
    for i in range(1, len(pts)):
        cv2.line(img, pts[i - 1], pts[i], color, 2)


# ---------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--weights", default="runs/detect/runs/bee11n/weights/best.pt")
    ap.add_argument("--zone", default=None, help="entrance_zone_*.txt from the dataset")
    ap.add_argument("--line", type=float, default=None,
                    help="fallback: entrance line as a fraction of frame height")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--csv", default=None)
    ap.add_argument("--events-csv", default=None)
    ap.add_argument("--dets-npz", default=None, help="dump per-frame detections for evaluation")
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--imgsz", type=int, default=960)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--band", type=float, default=0.025, help="slot half-band, fraction of height")
    ap.add_argument("--margin-above", type=float, default=0.12)
    ap.add_argument("--margin-below", type=float, default=0.10)
    ap.add_argument("--skip", type=int, default=2)
    ap.add_argument("--max-seconds", type=float, default=None)
    ap.add_argument("--no-intruder", action="store_true")
    ap.add_argument("--intruder-ratio", type=float, default=2.0,
                    help="unexplained motion blob area / median bee area to raise an alert")
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        sys.exit(f"cannot open {args.video}")
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    W0 = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H0 = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    W = args.width
    H = int(round(H0 * W / W0))
    fps = src_fps / args.skip
    band = H * args.band

    # ---- entrance geometry
    if args.zone:
        zone = load_zone(args.zone, W, H)
        entrance = Entrance.from_zone(zone, band)
    elif args.line is not None:
        zone = None
        entrance = Entrance.horizontal(W, H * args.line, band)
    else:
        sys.exit("need --zone or --line")

    roi = np.zeros((H, W), np.uint8)
    if zone is not None:
        poly = zone.copy()
        top = poly[:, 1].min()
        bot = poly[:, 1].max()
        poly[poly[:, 1] <= (top + bot) / 2, 1] -= H * args.margin_above
        poly[poly[:, 1] > (top + bot) / 2, 1] += H * args.margin_below
        cv2.fillPoly(roi, [poly.astype(np.int32)], 255)
    else:
        y0 = int(entrance.y_at(W / 2) - H * args.margin_above)
        y1 = int(entrance.y_at(W / 2) + H * args.margin_below)
        roi[max(0, y0):min(H, y1), :] = 255

    det = YoloDetector(args.weights, args.conf, args.imgsz)
    Track.reset()
    tracker = Tracker(max_dist=W * 0.05, max_age=int(fps * 0.6), min_hits=3, entrance=entrance)

    bg = cv2.createBackgroundSubtractorMOG2(history=400, varThreshold=30, detectShadows=True)
    bg.setShadowThreshold(0.6)

    writer = None
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(args.out, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))

    n_in = n_out = 0
    events = []
    rows = []
    per_min = deque(maxlen=120)
    counts_win = []
    frame_idx = 0
    processed = 0
    dets_dump = {}
    intruder_state = {}   # blob key -> consecutive frames
    n_intruder = 0
    t_infer = 0.0

    def count(kind, tr, rule, t):
        nonlocal n_in, n_out
        if tr.counted:
            return
        tr.counted = kind
        if kind == "IN":
            n_in += 1
        else:
            n_out += 1
        events.append(dict(t_s=round(t, 2), kind=kind, track=tr.id, rule=rule,
                           y0=round(tr.start[1], 1), y1=round(tr.last_seen[1], 1),
                           hits=tr.hits))

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

        t0 = cv2.getTickCount()
        boxes = det(small)
        t_infer += (cv2.getTickCount() - t0) / cv2.getTickFrequency()

        # keep only detections whose centre is inside the region of interest
        keep = []
        for b in boxes:
            cx, cy = int(b[0] + b[2] / 2), int(b[1] + b[3] / 2)
            if 0 <= cx < W and 0 <= cy < H and roi[cy, cx]:
                keep.append(b)
        boxes = keep
        if args.dets_npz is not None:
            dets_dump[str(frame_idx)] = np.array(boxes, dtype=np.float32).reshape(-1, 4)

        live, lost = tracker.step(boxes)

        # ---- counting
        for tr in live:
            side = entrance.side(tr.cx, tr.cy)
            if tr.side == "below" and side == "above":
                count("IN", tr, "cross", t)
            elif tr.side == "above" and side == "below":
                count("OUT", tr, "cross", t)
            elif (tr.origin_side in ("slot", "above") and side == "below"
                  and tr.hits >= 5 and tr.cy - tr.start[1] > 2 * band):
                count("OUT", tr, "emerge", t)
            tr.side = side
        for tr in lost:
            if (tr.counted is None and tr.origin_side == "below" and tr.hits >= 5
                    and entrance.side(*tr.last_seen) in ("slot", "above")
                    and tr.start[1] - tr.last_seen[1] > 2 * band):
                count("IN", tr, "vanish", t)

        # ---- intruder: motion the bee detector does not explain
        fg = None
        intruders = []
        if not args.no_intruder:
            fg = bg.apply(cv2.GaussianBlur(small, (5, 5), 0),
                          learningRate=(-1 if processed < fps * 2 else 0.004))
            fg = cv2.threshold(fg, 200, 255, cv2.THRESH_BINARY)[1]
            fg = cv2.bitwise_and(fg, roi)
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
            fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, k, 2)
            if processed > fps * 2:
                med = np.median([b[2] * b[3] for b in boxes]) if boxes else (W * 0.03) ** 2
                n, _, stats, cents = cv2.connectedComponentsWithStats(fg, 8)
                seen = set()
                for i in range(1, n):
                    x, y, w, h, a = stats[i]
                    if a < args.intruder_ratio * med:
                        continue
                    blob = (x, y, w, h)
                    if any(iou(blob, b) > 0.05 for b in boxes):
                        continue          # explained by one or more bees
                    key = (int(cents[i][0] // (W * 0.05)), int(cents[i][1] // (H * 0.05)))
                    seen.add(key)
                    intruder_state[key] = intruder_state.get(key, 0) + 1
                    if intruder_state[key] == int(fps * 1.5):
                        n_intruder += 1
                        events.append(dict(t_s=round(t, 2), kind="INTRUDER", track=-1,
                                           rule="unexplained-motion", y0=0, y1=0, hits=0))
                    if intruder_state[key] >= int(fps * 1.5):
                        intruders.append(blob)
                for key in list(intruder_state):
                    if key not in seen:
                        intruder_state[key] -= 2
                        if intruder_state[key] <= 0:
                            del intruder_state[key]

        counts_win.append(len(live))
        if len(counts_win) >= int(fps):
            rows.append(dict(t_s=round(t, 1),
                             bees_on_board=round(float(np.mean(counts_win)), 2),
                             in_total=n_in, out_total=n_out, intruder_events=n_intruder))
            per_min.append(float(np.mean(counts_win)))
            counts_win = []

        # ---- drawing
        if writer:
            vis = small
            if zone is not None:
                cv2.polylines(vis, [zone.astype(np.int32)], True, (120, 120, 120), 1)
            p0 = (int(entrance.p0[0]), int(entrance.y_at(entrance.p0[0])))
            p1 = (int(entrance.p1[0]), int(entrance.y_at(entrance.p1[0])))
            cv2.line(vis, p0, p1, (255, 255, 255), 2)
            put_label(vis, "HIVE", (W - 62, min(p0[1], p1[1]) - 8), 0.5)
            put_label(vis, "BOARD", (W - 62, max(p0[1], p1[1]) + 22), 0.5)
            for tr in live:
                x, y, w, h = [int(v) for v in tr.box]
                col = (0, 200, 0) if tr.counted == "IN" else ((0, 140, 255) if tr.counted == "OUT" else (255, 140, 0))
                cv2.rectangle(vis, (x, y), (x + w, y + h), col, 2)
                put_label(vis, str(tr.id), (x, max(11, y - 3)), 0.4, bg=col)
                pts = list(tr.trail)
                for i in range(1, len(pts)):
                    if math.dist(pts[i - 1], pts[i]) < W * 0.05:
                        cv2.line(vis, pts[i - 1], pts[i], col, 1)
            for (x, y, w, h) in intruders:
                cv2.rectangle(vis, (x, y), (x + w, y + h), (0, 0, 255), 3)
                put_label(vis, "INTRUDER?", (x, max(11, y - 3)), 0.5, bg=(0, 0, 255))
            for i, e in enumerate([e for e in events if 0 <= t - e["t_s"] < 1.2][-3:]):
                bgc = {"IN": (0, 150, 0), "OUT": (0, 120, 220)}.get(e["kind"], (0, 0, 200))
                put_label(vis, f'{e["kind"]} #{e["track"]}' if e["track"] > 0 else e["kind"],
                          (W // 2 - 40, 28 + 22 * i), 0.6, bg=bgc)
            draw_panel(vis, [f"IN: {n_in}   OUT: {n_out}",
                             f"bees on board: {len(live)}",
                             f"intruder alerts: {n_intruder}",
                             f"t = {t:6.1f}s"])
            sparkline(vis, list(per_min), (10, 130, 240, 46))
            put_label(vis, "activity", (14, 126), 0.4)
            writer.write(vis)

        if processed % int(fps * 10) == 0:
            print(f"t={t:6.1f}s  in={n_in} out={n_out} board={len(live)} "
                  f"intr={n_intruder}  {t_infer / processed * 1000:.0f} ms/frame", flush=True)

    cap.release()
    if writer:
        writer.release()
    if args.csv and rows:
        Path(args.csv).parent.mkdir(parents=True, exist_ok=True)
        with open(args.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    if args.events_csv and events:
        Path(args.events_csv).parent.mkdir(parents=True, exist_ok=True)
        with open(args.events_csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(events[0].keys()))
            w.writeheader()
            w.writerows(events)
    if args.dets_npz:
        Path(args.dets_npz).parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(args.dets_npz, **dets_dump)

    print("\n=== summary ===")
    print(f"video   : {args.video}")
    print(f"frames  : {processed} processed at {W}x{H}, {fps:.1f} fps")
    print(f"detector: {args.weights}  conf={args.conf} imgsz={args.imgsz}")
    print(f"speed   : {t_infer / max(processed,1) * 1000:.0f} ms/frame detection only")
    print(f"IN {n_in}   OUT {n_out}   net {n_in - n_out:+d}")
    print(f"intruder alerts: {n_intruder}")
    if rows:
        v = [r["bees_on_board"] for r in rows]
        print(f"bees on board: mean {np.mean(v):.1f}, max {np.max(v):.1f}")
    print("rules:", dict(Counter((e["kind"], e["rule"]) for e in events)))


if __name__ == "__main__":
    main()
