#!/usr/bin/env python3
"""
Beehaviour: bee detection, tracking, in/out counting and intruder alerting
at the hive entrance. Everything runs locally, no network needed.

Pipeline
  detection : YOLO, one class ("bee"), trained on hives the test videos never show
  tracking  : Hungarian assignment on predicted centroid distance + IoU
  counting  : the hive-side edge of the landing board is the entrance line.
              A bee does not walk across that line, it disappears INTO the
              slot, so "entered" is decided when a track is lost at the slot
              and the spot stays empty for a moment (delayed confirmation).
  intruder  : motion that the bee detector does not explain.

Rendering is decoupled from detection: detection runs on a small frame for
speed, the annotated video is drawn at full size next to a dashboard panel.
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

# ---------------------------------------------------------------- palette
C_PANEL = (34, 29, 24)
C_CARD = (48, 41, 34)
C_TEXT = (238, 238, 238)
C_DIM = (150, 150, 150)
C_IN = (90, 200, 90)
C_OUT = (80, 165, 245)
C_ALERT = (60, 60, 235)
C_TRACK = (235, 180, 90)
C_LINE = (255, 255, 255)
FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_B = cv2.FONT_HERSHEY_DUPLEX


# --------------------------------------------------------------- geometry
def load_zone(path, W, H):
    """Read `polygon = np.array([[x, y], ...])`, scaled from 1920x1080 to WxH."""
    nums = [int(n) for n in re.findall(r"-?\d+", Path(path).read_text())]
    pts = np.array(nums, dtype=float).reshape(-1, 2)
    pts[:, 0] *= W / 1920.0
    pts[:, 1] *= H / 1080.0
    return pts


class Entrance:
    """Hive-side edge of the landing board; may be sloped.

    Signed distance is positive below the line (outside, on the board) and
    negative above it (hive side).
    """

    def __init__(self, p0, p1, band):
        self.p0, self.p1 = np.asarray(p0, float), np.asarray(p1, float)
        self.band = band

    @classmethod
    def from_zone(cls, zone, band):
        idx = np.argsort(zone[:, 1])[:2]
        a, b = zone[idx[0]], zone[idx[1]]
        if a[0] > b[0]:
            a, b = b, a
        return cls(a, b, band)

    @classmethod
    def horizontal(cls, W, y, band):
        return cls((0.0, y), (float(W), y), band)

    def y_at(self, x):
        (x0, y0), (x1, y1) = self.p0, self.p1
        if abs(x1 - x0) < 1e-6:
            return y0
        return y0 + (y1 - y0) * (x - x0) / (x1 - x0)

    def dist(self, x, y):
        return y - self.y_at(x)

    def side(self, x, y):
        d = self.dist(x, y)
        return "above" if d < -self.band else ("below" if d > self.band else "slot")


# --------------------------------------------------------------- tracking
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

    def __init__(self, det, entrance, t):
        self.id = Track._next_id
        Track._next_id += 1
        self.box = self.last_box = det
        self.cx, self.cy = det[0] + det[2] / 2, det[1] + det[3] / 2
        self.vx = self.vy = 0.0
        self.hits = 1
        self.age = 0
        self.t0 = t
        self.trail = deque(maxlen=45)
        self.trail.append((self.cx, self.cy))
        self.start = (self.cx, self.cy)
        self.start_box = det
        self.born_clean = None
        self.last_seen = (self.cx, self.cy)
        self.side = entrance.side(self.cx, self.cy)
        self.origin_side = self.side
        self.counted = None

    def predict(self):
        return self.cx + self.vx, self.cy + self.vy

    def update(self, det):
        cx, cy = det[0] + det[2] / 2, det[1] + det[3] / 2
        a = 0.5
        self.vx = a * (cx - self.cx) + (1 - a) * self.vx
        self.vy = a * (cy - self.cy) + (1 - a) * self.vy
        self.cx, self.cy = cx, cy
        self.last_seen = (cx, cy)
        self.box = self.last_box = det
        self.hits += 1
        self.age = 0
        self.trail.append((cx, cy))

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

    def step(self, dets, t):
        if self.tracks and dets:
            pred = np.array([tr.predict() for tr in self.tracks])
            cent = np.array([[d[0] + d[2] / 2, d[1] + d[3] / 2] for d in dets])
            dist = np.linalg.norm(pred[:, None, :] - cent[None, :, :], axis=2)
            ious = np.array([[iou(tr.box, d) for d in dets] for tr in self.tracks])
            cost = dist / self.max_dist - 0.5 * ious
            cost[dist > self.max_dist] = 1e6
            rows, cols = linear_sum_assignment(cost)
            mt, md = set(), set()
            for r, c in zip(rows, cols):
                if cost[r, c] < 1e5:
                    self.tracks[r].update(dets[c])
                    mt.add(r)
                    md.add(c)
            for i, tr in enumerate(self.tracks):
                if i not in mt:
                    tr.coast()
            for j, d in enumerate(dets):
                if j not in md:
                    self.tracks.append(Track(d, self.entrance, t))
        elif dets:
            self.tracks += [Track(d, self.entrance, t) for d in dets]
        else:
            for tr in self.tracks:
                tr.coast()

        lost = [tr for tr in self.tracks if tr.age > self.max_age and tr.hits >= self.min_hits]
        self.tracks = [tr for tr in self.tracks if tr.age <= self.max_age]
        live = [tr for tr in self.tracks if tr.hits >= self.min_hits and tr.age == 0]
        return live, lost


# --------------------------------------------------------------- detector
class YoloDetector:
    def __init__(self, weights, conf, imgsz):
        from ultralytics import YOLO
        self.model = YOLO(weights)
        self.conf, self.imgsz = conf, imgsz

    def __call__(self, frame):
        r = self.model.predict(frame, conf=self.conf, imgsz=self.imgsz,
                               verbose=False, max_det=300)[0]
        b = r.boxes.xyxy.cpu().numpy()
        return [(float(x0), float(y0), float(x1 - x0), float(y1 - y0))
                for x0, y0, x1, y1 in b]


# ---------------------------------------------------------------- drawing
def text(img, s, org, scale=0.5, color=C_TEXT, thick=1, font=FONT, shadow=True):
    x, y = int(org[0]), int(org[1])
    if shadow:
        cv2.putText(img, s, (x + 1, y + 1), font, scale, (0, 0, 0), thick + 1, cv2.LINE_AA)
    cv2.putText(img, s, (x, y), font, scale, color, thick, cv2.LINE_AA)


def chip(img, s, org, color, scale=0.5, pad=5):
    (tw, th), base = cv2.getTextSize(s, FONT, scale, 1)
    x, y = int(org[0]), int(org[1])
    cv2.rectangle(img, (x, y - th - pad), (x + tw + 2 * pad, y + base + pad - 2), color, -1)
    cv2.putText(img, s, (x + pad, y), FONT, scale, (255, 255, 255), 1, cv2.LINE_AA)


def rounded(img, p0, p1, color, r=8):
    x0, y0 = p0
    x1, y1 = p1
    cv2.rectangle(img, (x0 + r, y0), (x1 - r, y1), color, -1)
    cv2.rectangle(img, (x0, y0 + r), (x1, y1 - r), color, -1)
    for cx, cy in ((x0 + r, y0 + r), (x1 - r, y0 + r), (x0 + r, y1 - r), (x1 - r, y1 - r)):
        cv2.circle(img, (cx, cy), r, color, -1)


def draw_sparkline(img, box, values, color, label=""):
    x, y, w, h = box
    rounded(img, (x, y), (x + w, y + h), C_CARD, 6)
    if label:
        text(img, label, (x + 10, y + 17), 0.4, C_DIM, 1, shadow=False)
    if len(values) < 2:
        return
    vmax = max(max(values), 1.0)
    top, hh = y + 24, h - 32
    pts = []
    for i, v in enumerate(values):
        px = x + 10 + int(i * (w - 20) / (len(values) - 1))
        py = top + hh - int(min(v / vmax, 1.0) * hh)
        pts.append((px, py))
    poly = np.array(pts + [(pts[-1][0], top + hh), (pts[0][0], top + hh)], np.int32)
    ov = img.copy()
    cv2.fillPoly(ov, [poly], color)
    cv2.addWeighted(ov, 0.22, img, 0.78, 0, img)
    cv2.polylines(img, [np.array(pts, np.int32)], False, color, 2, cv2.LINE_AA)
    text(img, f"{vmax:.0f}", (x + w - 34, y + 17), 0.4, C_DIM, 1, shadow=False)


def build_panel(PW, PH, st):
    """Right-hand dashboard."""
    p = np.full((PH, PW, 3), C_PANEL, np.uint8)
    cv2.rectangle(p, (0, 0), (2, PH), (70, 60, 50), -1)
    y = 40
    text(p, "BEEHAVIOUR", (18, y), 0.85, C_TEXT, 2, FONT_B, shadow=False)
    y += 22
    text(p, "guardian de colmena  ·  100% local", (18, y), 0.42, C_DIM, 1, shadow=False)
    y += 22
    cv2.line(p, (18, y), (PW - 18, y), (70, 60, 50), 1)

    y += 22
    bw = (PW - 46) // 2
    for i, (lbl, val, col) in enumerate((("ENTRAN", st["n_in"], C_IN),
                                         ("SALEN", st["n_out"], C_OUT))):
        x0 = 18 + i * (bw + 10)
        rounded(p, (x0, y), (x0 + bw, y + 80), C_CARD, 8)
        text(p, lbl, (x0 + 12, y + 22), 0.45, C_DIM, 1, shadow=False)
        text(p, str(val), (x0 + 12, y + 66), 1.4, col, 3, FONT_B, shadow=False)
    y += 94

    rounded(p, (18, y), (PW - 18, y + 60), C_CARD, 8)
    text(p, "ABEJAS EN LA TABLA", (30, y + 22), 0.44, C_DIM, 1, shadow=False)
    text(p, str(st["on_board"]), (30, y + 50), 0.95, C_TEXT, 2, FONT_B, shadow=False)
    text(p, f"max {st['max_board']}", (PW - 108, y + 50), 0.5, C_DIM, 1, shadow=False)
    y += 74

    draw_sparkline(p, (18, y, PW - 36, 88), st["spark"], C_TRACK,
                   label="ACTIVIDAD (abejas/s)")
    y += 102

    if st["n_intruder"]:
        col = C_ALERT if st["alert_now"] else (44, 40, 110)
        rounded(p, (18, y), (PW - 18, y + 52), col, 8)
        text(p, "! INTRUSO DETECTADO", (32, y + 23), 0.5, (255, 255, 255), 1, shadow=False)
        text(p, f"{st['n_intruder']} aviso(s) · algo que no es abeja",
             (32, y + 42), 0.37, (235, 235, 235), 1, shadow=False)
    else:
        rounded(p, (18, y), (PW - 18, y + 52), C_CARD, 8)
        text(p, "sin intrusos", (32, y + 24), 0.48, C_IN, 1, shadow=False)
        text(p, "vigilando la piquera", (32, y + 42), 0.37, C_DIM, 1, shadow=False)
    y += 68

    text(p, "ULTIMOS EVENTOS", (18, y + 12), 0.44, C_DIM, 1, shadow=False)
    y += 28
    for e in st["events"][-8:][::-1]:
        if y > PH - 56:
            break
        col = {"IN": C_IN, "OUT": C_OUT}.get(e["kind"], C_ALERT)
        cv2.circle(p, (26, y - 4), 4, col, -1)
        lbl = {"IN": "entra", "OUT": "sale"}.get(e["kind"], "INTRUSO")
        text(p, f"{e['t_s']:6.1f}s", (40, y), 0.42, C_DIM, 1, shadow=False)
        text(p, lbl, (110, y), 0.42, col, 1, shadow=False)
        if e["track"] > 0:
            text(p, f"#{e['track']}", (178, y), 0.42, C_DIM, 1, shadow=False)
        y += 21

    text(p, st["footer"], (18, PH - 32), 0.38, C_DIM, 1, shadow=False)
    text(p, st["footer2"], (18, PH - 14), 0.38, C_DIM, 1, shadow=False)
    return p


# ------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--weights", default="models/bee11n.pt")
    ap.add_argument("--zone", default=None, help="entrance_zone_*.txt from the dataset")
    ap.add_argument("--line", type=float, default=None,
                    help="fallback: entrance line as a fraction of frame height")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--csv", default=None)
    ap.add_argument("--events-csv", default=None)
    ap.add_argument("--dets-npz", default=None)
    ap.add_argument("--width", type=int, default=960, help="detection width")
    ap.add_argument("--render-width", type=int, default=1280, help="video width in the output")
    ap.add_argument("--panel", type=int, default=340, help="dashboard width, 0 to disable")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--conf", type=float, default=0.40)
    ap.add_argument("--band", type=float, default=0.025)
    ap.add_argument("--margin-above", type=float, default=0.12)
    ap.add_argument("--margin-below", type=float, default=0.10)
    ap.add_argument("--skip", type=int, default=2)
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--max-seconds", type=float, default=None)
    ap.add_argument("--title", default=None)
    ap.add_argument("--no-intruder", action="store_true")
    ap.add_argument("--intruder-ratio", type=float, default=2.0)
    ap.add_argument("--confirm-delay", type=float, default=0.8,
                    help="seconds a vanished bee's spot must stay empty before counting it IN")
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        sys.exit(f"cannot open {args.video}")
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    W0 = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H0 = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    W = args.width
    H = int(round(H0 * W / W0))
    RW = args.render_width
    RH = int(round(H0 * RW / W0))
    sc = RW / W
    fps = src_fps / args.skip
    band = H * args.band
    if args.start:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(args.start * src_fps))

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
        mid = (poly[:, 1].min() + poly[:, 1].max()) / 2
        poly[poly[:, 1] <= mid, 1] -= H * args.margin_above
        poly[poly[:, 1] > mid, 1] += H * args.margin_below
        cv2.fillPoly(roi, [poly.astype(np.int32)], 255)
    else:
        y0 = int(entrance.y_at(W / 2) - H * args.margin_above)
        y1 = int(entrance.y_at(W / 2) + H * args.margin_below)
        roi[max(0, y0):min(H, y1), :] = 255

    roi_poly_r = np.array(
        (poly if zone is not None else np.array(
            [[0, y0], [W, y0], [W, y1], [0, y1]], float)) * sc, np.int32)
    soft_mask = (cv2.resize(roi, (RW, RH), interpolation=cv2.INTER_NEAREST) / 255.0).astype(np.float32)

    det = YoloDetector(args.weights, args.conf, args.imgsz)
    Track.reset()
    tracker = Tracker(W * 0.05, int(fps * 0.6), 3, entrance)

    bg = cv2.createBackgroundSubtractorMOG2(history=400, varThreshold=30, detectShadows=True)
    bg.setShadowThreshold(0.6)

    PW = args.panel
    writer = None
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(args.out, cv2.VideoWriter_fourcc(*"mp4v"), fps, (RW + PW, RH))

    n_in = n_out = n_intruder = 0
    max_board = 0
    events, rows = [], []
    spark = deque(maxlen=150)
    win = []
    pending = []
    recent_boxes = deque(maxlen=max(2, int(fps * 0.7)))
    intruder_state, last_alert_t = {}, -99.0
    dets_dump = {}
    frame_idx = int(args.start * src_fps)
    processed = 0
    t_infer = 0.0
    flashes = []

    def add_event(kind, t, tid):
        nonlocal n_in, n_out
        if kind == "IN":
            n_in += 1
        elif kind == "OUT":
            n_out += 1
        events.append(dict(t_s=round(t, 2), kind=kind, track=tid))

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame_idx += 1
        if (frame_idx - 1) % args.skip:
            continue
        t = frame_idx / src_fps - args.start
        if args.max_seconds and t > args.max_seconds:
            break
        processed += 1

        small = cv2.resize(frame, (W, H), interpolation=cv2.INTER_AREA)
        t0 = cv2.getTickCount()
        boxes = det(small)
        t_infer += (cv2.getTickCount() - t0) / cv2.getTickFrequency()

        boxes = [b for b in boxes
                 if 0 <= int(b[0] + b[2] / 2) < W and 0 <= int(b[1] + b[3] / 2) < H
                 and roi[int(b[1] + b[3] / 2), int(b[0] + b[2] / 2)]]
        if args.dets_npz is not None:
            dets_dump[str(frame_idx)] = np.array(boxes, np.float32).reshape(-1, 4)

        prev_boxes = list(recent_boxes)
        live, lost = tracker.step(boxes, t)
        for tr in tracker.tracks:
            if tr.hits == 1 and tr.age == 0 and tr.born_clean is None:
                tr.born_clean = not any(iou(tr.start_box, b) > 0.05
                                        for fb in prev_boxes for b in fb)
        recent_boxes.append(boxes)

        # --------------------------------------------------------- counting
        for tr in live:
            side = entrance.side(tr.cx, tr.cy)
            if tr.counted is None:
                if tr.side == "below" and side == "above":
                    tr.counted = "IN"
                    add_event("IN", t, tr.id)
                    flashes.append((t, "IN", tr.cx, tr.cy, tr.id))
                elif tr.side == "above" and side == "below":
                    tr.counted = "OUT"
                    add_event("OUT", t, tr.id)
                    flashes.append((t, "OUT", tr.cx, tr.cy, tr.id))
                elif (tr.origin_side == "slot" and side == "below"
                      and tr.hits >= 6 and tr.cy - tr.start[1] > 3 * band and tr.vy > 0
                      and tr.born_clean):
                    tr.counted = "OUT"
                    add_event("OUT", t, tr.id)
                    flashes.append((t, "OUT", tr.cx, tr.cy, tr.id))
            tr.side = side

        # A bee that vanishes at the slot has probably gone inside, but the
        # detector also drops bees now and then. Hold the decision and only
        # confirm it if nothing reappears on that spot.
        for tr in lost:
            if (tr.counted is None and tr.origin_side == "below" and tr.hits >= 5
                    and entrance.side(*tr.last_seen) == "slot"
                    and tr.start[1] - tr.last_seen[1] > 2 * band
                    and tr.vy <= 0.5
                    and not any(iou(tr.last_box, b) > 0.05 for b in boxes)):
                pending.append(dict(t=t, box=tr.last_box, pos=tr.last_seen, id=tr.id))

        still = []
        for p in pending:
            if any(iou(p["box"], b) > 0.05 or
                   math.dist(p["pos"], (b[0] + b[2] / 2, b[1] + b[3] / 2)) < W * 0.02
                   for b in boxes):
                continue                      # detector miss, not an entry
            if t - p["t"] >= args.confirm_delay:
                add_event("IN", p["t"], p["id"])
                flashes.append((t, "IN", p["pos"][0], p["pos"][1], p["id"]))
            else:
                still.append(p)
        pending = still

        # --------------------------------------------------------- intruder
        alert_boxes = []
        if not args.no_intruder:
            fg = bg.apply(cv2.GaussianBlur(small, (5, 5), 0),
                          learningRate=(-1 if processed < fps * 2 else 0.004))
            fg = cv2.bitwise_and(cv2.threshold(fg, 200, 255, cv2.THRESH_BINARY)[1], roi)
            fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE,
                                  cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)), 2)
            if processed > fps * 2:
                med = np.median([b[2] * b[3] for b in boxes]) if boxes else (W * 0.03) ** 2
                n, _, stats, cents = cv2.connectedComponentsWithStats(fg, 8)
                seen = set()
                for i in range(1, n):
                    x, y, w, h, a = stats[i]
                    if a < args.intruder_ratio * med:
                        continue
                    if any(iou((x, y, w, h), b) > 0.05 for b in boxes):
                        continue
                    key = (int(cents[i][0] // (W * 0.05)), int(cents[i][1] // (H * 0.05)))
                    seen.add(key)
                    intruder_state[key] = intruder_state.get(key, 0) + 1
                    if intruder_state[key] == int(fps * 1.5):
                        n_intruder += 1
                        events.append(dict(t_s=round(t, 2), kind="INTRUDER", track=-1))
                    if intruder_state[key] >= int(fps * 1.5):
                        alert_boxes.append((x, y, w, h))
                        last_alert_t = t
                for key in list(intruder_state):
                    if key not in seen:
                        intruder_state[key] -= 2
                        if intruder_state[key] <= 0:
                            del intruder_state[key]

        # ------------------------------------------------------------ stats
        win.append(len(live))
        max_board = max(max_board, len(live))
        if len(win) >= int(fps):
            m = float(np.mean(win))
            spark.append(m)
            rows.append(dict(t_s=round(t, 1), bees_on_board=round(m, 2),
                             in_total=n_in, out_total=n_out, intruder_events=n_intruder))
            win = []

        # ---------------------------------------------------------- drawing
        if writer:
            vis = cv2.resize(frame, (RW, RH), interpolation=cv2.INTER_AREA)
            a = cv2.GaussianBlur(soft_mask, (0, 0), RW * 0.012)[:, :, None]
            vis = (vis * (0.60 + 0.40 * a)).astype(np.uint8)
            cv2.polylines(vis, [roi_poly_r], True, (110, 95, 80), 1, cv2.LINE_AA)

            p0 = (0, int(entrance.y_at(0) * sc))
            p1 = (RW, int(entrance.y_at(W) * sc))
            cv2.line(vis, p0, p1, C_LINE, 2, cv2.LINE_AA)
            text(vis, "COLMENA", (RW - 120, min(p0[1], p1[1]) - 12), 0.5, C_LINE, 1)
            text(vis, "TABLA DE VUELO", (RW - 176, max(p0[1], p1[1]) + 26), 0.5, C_LINE, 1)

            for tr in live:
                x, y, w, h = [int(v * sc) for v in tr.box]
                col = {"IN": C_IN, "OUT": C_OUT}.get(tr.counted, C_TRACK)
                cv2.rectangle(vis, (x, y), (x + w, y + h), col, 2, cv2.LINE_AA)
                text(vis, str(tr.id), (x, y - 5), 0.4, col, 1)
                pts = [(int(a * sc), int(b * sc)) for a, b in tr.trail]
                for i in range(1, len(pts)):
                    if math.dist(pts[i - 1], pts[i]) < RW * 0.05:
                        f = 0.35 + 0.65 * i / len(pts)
                        cv2.line(vis, pts[i - 1], pts[i],
                                 tuple(int(c * f) for c in col), 1, cv2.LINE_AA)

            for (x, y, w, h) in alert_boxes:
                x, y, w, h = int(x * sc), int(y * sc), int(w * sc), int(h * sc)
                cv2.rectangle(vis, (x - 4, y - 4), (x + w + 4, y + h + 4), C_ALERT, 3, cv2.LINE_AA)
                chip(vis, "INTRUSO", (x - 4, y - 12), C_ALERT, 0.5)

            flashes = [f for f in flashes if t - f[0] < 1.0]
            used = []
            for ft, kind, fx, fy, fid in flashes:
                age = t - ft
                cx, cy = int(fx * sc), int(fy * sc)
                r = int(12 + 30 * age)
                col = C_IN if kind == "IN" else C_OUT
                cv2.circle(vis, (cx, cy), r, col, 2, cv2.LINE_AA)
                lx, ly = cx + r + 6, cy + 6
                while any(abs(ly - uy) < 22 and abs(lx - ux) < 150 for ux, uy in used):
                    ly += 24
                used.append((lx, ly))
                chip(vis, ("ENTRA #" if kind == "IN" else "SALE #") + str(fid),
                     (lx, ly), col, 0.48)

            if PW:
                panel = build_panel(PW, RH, dict(
                    n_in=n_in, n_out=n_out, on_board=len(live), max_board=max_board,
                    spark=list(spark), n_intruder=n_intruder,
                    alert_now=(t - last_alert_t) < 2.0, events=events,
                    footer=f"YOLO11n · {t_infer / max(processed, 1) * 1000:.0f} ms/frame",
                    footer2=f"t = {t:6.1f} s  ·  {args.title or Path(args.video).stem}"))
                canvas = np.hstack([vis, panel])
            else:
                canvas = vis
            writer.write(canvas)

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
    print(f"frames  : {processed} processed, detection {W}x{H}, render {RW}x{RH}, {fps:.1f} fps")
    print(f"detector: {args.weights}  conf={args.conf} imgsz={args.imgsz}")
    print(f"speed   : {t_infer / max(processed, 1) * 1000:.0f} ms/frame detection only")
    print(f"IN {n_in}   OUT {n_out}   net {n_in - n_out:+d}")
    print(f"intruder alerts: {n_intruder}")
    if rows:
        v = [r["bees_on_board"] for r in rows]
        print(f"bees on board: mean {np.mean(v):.1f}, max {np.max(v):.1f}")
    print("events:", dict(Counter(e["kind"] for e in events)))


if __name__ == "__main__":
    main()
