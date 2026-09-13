#!/usr/bin/env python3
"""
Top instrument strip for the annotated video: yellow and white on black,
monospaced, hairline separators. English labels.

Kept apart from the pipeline so the readout can be redesigned without
touching detection or counting.
"""
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# DejaVu Sans Mono, looked up where each system keeps it. The readout is
# monospaced by design: columns of numbers must not jitter between frames.
_FONT_DIRS = (
    "/usr/share/fonts/truetype/dejavu",          # Debian, Ubuntu
    "/usr/share/fonts/dejavu",                   # Fedora, Arch
    "/usr/share/fonts/dejavu-sans-mono-fonts",   # RHEL
    "/opt/homebrew/share/fonts",                 # macOS, brew font-dejavu
    "/usr/local/share/fonts",
)


def _find_font(*names):
    for d in _FONT_DIRS:
        for n in names:
            p = Path(d) / n
            if p.exists():
                return str(p)
    return None


MONO = _find_font("DejaVuSansMono.ttf")
MONO_B = _find_font("DejaVuSansMono-Bold.ttf", "DejaVuSansMono.ttf")

BLACK = (8, 8, 8)
WHITE = (245, 245, 243)
GREY = (122, 120, 116)
FAINT = (58, 56, 52)
HAIR = (40, 39, 37)
YELLOW = (247, 200, 42)
RED = (226, 66, 48)

# BGR versions for the OpenCV side (the video itself)
B_WHITE = WHITE[::-1]
B_YELLOW = YELLOW[::-1]
B_RED = RED[::-1]
B_GREY = (150, 150, 150)

_fonts = {}


def font(path, size):
    key = (path, size)
    if key not in _fonts:
        if path is None:
            # No DejaVu on this machine: the strip still renders, just uglier.
            _fonts[key] = ImageFont.load_default(size)
        else:
            _fonts[key] = ImageFont.truetype(path, size)
    return _fonts[key]


def _w(d, s, f):
    b = d.textbbox((0, 0), s, font=f)
    return b[2] - b[0]


def hex_pulse(d, cx, cy, r, col=WHITE, acc=YELLOW, w=2):
    pts = [(cx + r * math.cos(math.radians(60 * i + 30)),
            cy + r * math.sin(math.radians(60 * i + 30))) for i in range(6)]
    d.polygon(pts, outline=col, width=w)
    a = r * 0.62
    d.line([(cx - a, cy), (cx - a * .45, cy), (cx - a * .2, cy - r * .42),
            (cx + a * .06, cy + r * .40), (cx + a * .3, cy - r * .12),
            (cx + a * .52, cy), (cx + a, cy)],
           fill=acc, width=max(2, r // 8), joint="curve")


def _chart(d, box, vals, col=YELLOW):
    x0, y0, x1, y1 = box
    if len(vals) < 2:
        return 0
    vmax = max(max(vals), 1)
    for k in (1, 2):
        yy = y1 - k * (y1 - y0) / 3
        d.line([(x0, yy), (x1, yy)], fill=HAIR, width=1)
    pts = [(x0 + i * (x1 - x0) / (len(vals) - 1), y1 - (v / vmax) * (y1 - y0))
           for i, v in enumerate(vals)]
    d.line(pts, fill=col, width=2, joint="curve")
    return vmax


def build_strip(W, H, st):
    """Return a BGR image of the readout strip."""
    im = Image.new("RGB", (W, H), BLACK)
    d = ImageDraw.Draw(im)
    pad = 22
    y0, y1 = 12, H - 12
    mid = H // 2

    hex_pulse(d, pad + 12, mid - 4, 12, WHITE, YELLOW, 2)
    d.text((pad + 30, mid - 18), "BEEHAVIOUR", font=font(MONO_B, 16), fill=WHITE)
    d.text((pad + 31, mid + 2), st.get("hive", "HIVE 01"), font=font(MONO, 10), fill=GREY)
    x = pad + 146
    d.line([(x, y0), (x, y1)], fill=HAIR)

    def cell(x, lbl, val, col, big=34, w=118):
        d.text((x + 16, mid - 20), lbl, font=font(MONO, 10), fill=GREY)
        d.text((x + 16, mid - 8), str(val), font=font(MONO_B, big), fill=col)
        d.line([(x + w, y0), (x + w, y1)], fill=HAIR)
        return x + w

    x = cell(x, "BEES IN", st["n_in"], YELLOW)
    x = cell(x, "BEES OUT", st["n_out"], WHITE)
    x = cell(x, "ON BOARD", st["on_board"], WHITE, 24, 110)
    x = cell(x, "PEAK", st["peak"], GREY, 24, 92)

    cw = 300
    d.text((x + 16, mid - 20), "ACTIVITY", font=font(MONO, 10), fill=GREY)
    vmax = _chart(d, (x + 16, mid - 6, x + cw - 12, y1 - 10), st["spark"])
    lab = f"{vmax:.0f}/s"
    d.text((x + cw - 12 - _w(d, lab, font(MONO, 9)), mid - 19), lab,
           font=font(MONO, 9), fill=FAINT)
    x += cw
    d.line([(x, y0), (x, y1)], fill=HAIR)

    if st.get("alert"):
        d.text((x + 16, mid - 20), "ALERT", font=font(MONO, 10), fill=GREY)
        d.text((x + 16, mid - 6), "! INTRUDER", font=font(MONO_B, 17), fill=RED)
    else:
        d.text((x + 16, mid - 20), "LOG", font=font(MONO, 10), fill=GREY)
        yy = mid - 8
        for tt, kind, tid in st["events"][:2]:
            d.text((x + 16, yy), f"{tt:>5.1f}s", font=font(MONO, 11), fill=GREY)
            d.text((x + 74, yy), kind, font=font(MONO_B, 11),
                   fill=YELLOW if kind == "IN" else WHITE)
            d.text((x + 118, yy), tid, font=font(MONO, 11), fill=FAINT)
            yy += 16

    t = st["clock"]
    d.text((W - pad - _w(d, t, font(MONO, 11)), y0 + 2), t, font=font(MONO, 11), fill=GREY)
    foot = st.get("footer", "ON-DEVICE")
    d.text((W - pad - _w(d, foot, font(MONO, 9)), y1 - 12), foot,
           font=font(MONO, 9), fill=FAINT)

    img = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
    cv2.line(img, (0, H - 1), (W, H - 1), B_YELLOW, 1)
    return img
