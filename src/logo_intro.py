#!/usr/bin/env python3
"""Animated BEEHAVIOUR logo intro (hex-pulse mark) rendered to mp4.

Beats: the hexagon traces itself, the ECG pulse draws left to right, the beat
flashes, the wordmark wipes in, and a highlight keeps sweeping the pulse while
the block holds.  Geometry, palette and the two brand blocks match
src/mock_panels.py and out/mocks/logos.png.
"""
import argparse
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

F = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FC = "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf"
FCB = "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"

BG = (20, 18, 16)
TEXT = (238, 236, 232)
DIM = (150, 142, 132)
ACCENT = (224, 168, 60)
RULE = (60, 52, 44)

# The wordmark block from out/mocks/logos.png, per language.
LOCKUPS = {
    "en": dict(face=FCB, body=FC, size=112,
               tag="hive watch \u00b7 colony protection"),
    "es": dict(face=FCB, body=FC, size=112,
               tag="guardi\u00e1n de colmena \u00b7 sin conexi\u00f3n"),
}

_cache = {}


def font(path, size):
    key = (path, int(size))
    if key not in _cache:
        _cache[key] = ImageFont.truetype(path, int(size))
    return _cache[key]


# ----------------------------------------------------------------- easing
def clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def seg(t, a, b):
    """Normalised progress of t inside the window [a, b]."""
    return clamp((t - a) / (b - a)) if b > a else float(t >= b)


def ease_out(x):
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


# ---------------------------------------------------------------- geometry
def hexagon(cx, cy, r, rot=30):
    return [(cx + r * math.cos(math.radians(60 * i + rot)),
             cy + r * math.sin(math.radians(60 * i + rot))) for i in range(6)]


def pulse_points(cx, cy, r):
    """The ECG polyline from mark_hex_pulse()."""
    w = r * 0.62
    return [(cx - w, cy), (cx - w * 0.45, cy), (cx - w * 0.2, cy - r * 0.42),
            (cx + w * 0.06, cy + r * 0.40), (cx + w * 0.3, cy - r * 0.12),
            (cx + w * 0.52, cy), (cx + w, cy)]


def arclen(pts):
    acc = [0.0]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        acc.append(acc[-1] + math.hypot(x1 - x0, y1 - y0))
    return acc


def sub(pts, d0, d1):
    """Sub-polyline between two arc lengths, keeping the original vertices.

    Drawing through the real corners instead of a dense resampling keeps PIL
    from leaving stepped notches along a thick stroke.
    """
    acc = arclen(pts)
    d0, d1 = max(0.0, d0), min(acc[-1], d1)
    if d1 <= d0:
        return []

    def at(d):
        j = max(k for k in range(len(acc) - 1) if acc[k] <= d)
        span = acc[j + 1] - acc[j] or 1.0
        f = (d - acc[j]) / span
        x0, y0 = pts[j]
        x1, y1 = pts[j + 1]
        return (x0 + (x1 - x0) * f, y0 + (y1 - y0) * f), j

    p0, j0 = at(d0)
    p1, j1 = at(d1)
    return [p0] + pts[j0 + 1:j1 + 1] + [p1]


def trace(pts, frac):
    return sub(pts, 0.0, clamp(frac) * arclen(pts)[-1])


# ------------------------------------------------------------------ layers
def glow(layer, radius, gain=1.0):
    g = layer.filter(ImageFilter.GaussianBlur(radius))
    if gain != 1.0:
        a = g.split()[3].point(lambda v: min(255, int(v * gain)))
        g.putalpha(a)
    return g


def add(base, layer):
    base.alpha_composite(layer)


def rgba(col, alpha):
    return (col[0], col[1], col[2], int(clamp(alpha) * 255))


# ------------------------------------------------------------------- frame
def draw_frame(t, W, H, dur, lk=LOCKUPS["en"]):
    img = Image.new("RGBA", (W, H), BG + (255,))
    S = H / 1080.0                      # scale factor from the 1080p design

    # -------- timeline
    p_hex = ease_out(seg(t, 0.15, 1.15))        # hexagon traces itself
    p_pulse = seg(t, 0.75, 1.75)                # ECG draws across
    beat = seg(t, 1.60, 2.05)                   # flash on the beat
    p_move = ease_in_out(seg(t, 1.85, 2.55))    # mark slides to final spot
    p_word = seg(t, 2.15, 2.95)                 # wordmark wipes in
    p_tag = seg(t, 2.70, 3.35)                  # tagline + rule
    p_out = seg(t, dur - 0.75, dur - 0.05)      # fade to background

    # -------- layout: centred mark -> logo block on the left of the lockup
    r = 126 * S
    f_word = font(lk["face"], lk["size"] * S)
    f_tag = font(lk["body"], 38 * S)
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    word_w = probe.textlength("BEEHAVIOUR", font=f_word)
    gap = r * 0.60
    block_w = 2 * r + gap + word_w
    cy = H / 2 - 12 * S                         # optical centre of the lockup
    cx_solo = W / 2
    cx_end = W / 2 - block_w / 2 + r
    cx = cx_solo + (cx_end - cx_solo) * p_move
    text_x = cx + r + gap

    ink = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hot = Image.new("RGBA", (W, H), (0, 0, 0, 0))   # feeds the glow pass
    d = ImageDraw.Draw(ink)
    dh = ImageDraw.Draw(hot)

    # -------- ghost comb behind the mark
    a_comb = seg(t, 0.45, 1.45) * 0.30 * (1 - 0.45 * p_move)
    if a_comb > 0.01:
        s = r * 0.92
        for k, (dx, dy) in enumerate([(-1, -0.5), (1, -0.5), (-1, 0.5),
                                      (1, 0.5), (0, -1), (0, 1)]):
            fade = clamp(seg(t, 0.45 + k * 0.05, 1.25 + k * 0.05))
            d.polygon(hexagon(cx + dx * s * 1.5, cy + dy * s * 1.75, s),
                      outline=rgba(RULE, a_comb * fade * 1.8),
                      width=max(1, int(r / 22)))

    # -------- hexagon traced from the top vertex
    corners = hexagon(cx, cy, r)
    ring = corners[4:] + corners[:4] + [corners[4]]    # start up top, clockwise
    lw = max(2, int(r / 9))
    if p_hex >= 1:
        d.polygon(corners, outline=rgba(TEXT, 1.0), width=lw)
    else:
        seen = trace(ring, p_hex)
        if len(seen) > 1:
            d.line(seen, fill=rgba(TEXT, 1.0), width=lw, joint="curve")
            hx, hy = seen[-1]                          # bright drawing head
            dh.ellipse([hx - lw, hy - lw, hx + lw, hy + lw],
                       fill=rgba(TEXT, 0.9))

    # -------- ECG pulse
    path = pulse_points(cx, cy, r)
    pw = max(2, int(r / 8))
    drawn = trace(path, p_pulse)
    if len(drawn) > 1:
        d.line(drawn, fill=rgba(ACCENT, 1.0), width=pw, joint="curve")
        dh.line(drawn, fill=rgba(ACCENT, 0.55), width=pw, joint="curve")
        if p_pulse < 1:
            hx, hy = drawn[-1]
            dh.ellipse([hx - pw, hy - pw, hx + pw, hy + pw],
                       fill=rgba(ACCENT, 1.0))

    # -------- the beat: a ring pushing out of the mark
    if 0 < beat < 1:
        e = ease_out(beat)
        d.polygon(hexagon(cx, cy, r * (1 + 0.45 * e)),
                  outline=rgba(ACCENT, (1 - e) * 0.55),
                  width=max(1, int(lw * (1 - e) + 1)))
        dh.polygon(hexagon(cx, cy, r), outline=rgba(ACCENT, (1 - e) * 0.8),
                   width=lw)

    # -------- highlight sweeping the pulse once it is settled
    if p_pulse >= 1:
        loop = ((t - 1.75) % 2.2) / 2.2
        if loop < 0.45:
            k = loop / 0.45
            total = arclen(path)[-1]
            head = k * (total + r * 0.5)
            piece = sub(path, head - r * 0.5, head)
            fade = math.sin(math.pi * k) ** 2
            if len(piece) > 1:
                d.line(piece, fill=rgba((255, 216, 140), fade * 0.85),
                       width=pw, joint="curve")
                dh.line(piece, fill=rgba(ACCENT, fade * 0.6), width=pw,
                        joint="curve")

    # -------- wordmark, revealed by a left-to-right wipe
    if p_word > 0:
        word = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(word).text((text_x, cy + 6 * S), "BEEHAVIOUR",
                                  font=f_word, anchor="ls", fill=rgba(TEXT, 1.0))
        mask = Image.new("L", (W, H), 0)
        soft = 90 * S
        edge = text_x - soft + (word_w + 2 * soft) * ease_out(p_word)
        md = ImageDraw.Draw(mask)
        md.rectangle([0, 0, edge - soft, H], fill=255)
        for i in range(int(soft)):                      # soft leading edge
            x = edge - soft + i
            md.line([(x, 0), (x, H)], fill=int(255 * (1 - i / soft)))
        a = word.split()[3].point(lambda v: v)
        word.putalpha(Image.composite(a, Image.new("L", (W, H), 0), mask))
        add(ink, word)

    # -------- rule + tagline
    if p_tag > 0:
        y = cy + 34 * S
        x1 = text_x + word_w * ease_out(p_tag)
        d.line([(text_x + 2 * S, y), (max(text_x + 2 * S, x1), y)],
               fill=rgba(ACCENT, 0.8), width=max(1, int(3 * S)))
        d.text((text_x + 3 * S, y + 20 * S), lk["tag"],
               font=f_tag, fill=rgba(DIM, ease_out(p_tag)))

    add(ink, glow(hot, 18 * S, 1.0))
    add(ink, glow(hot, 48 * S, 0.55))
    add(img, ink)

    if p_out > 0:                                    # fade out to background
        img.alpha_composite(Image.new("RGBA", (W, H),
                                      BG + (int(255 * ease_in_out(p_out)),)))
    return img.convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/brand/beehaviour_intro_en.mp4")
    ap.add_argument("--lang", choices=sorted(LOCKUPS), default="en")
    ap.add_argument("--tagline", help="override the tagline text")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--duration", type=float, default=5.5)
    ap.add_argument("--ss", type=int, default=2, help="supersampling factor")
    ap.add_argument("--poster", action="store_true",
                    help="also write a still of the final lockup")
    a = ap.parse_args()

    lk = dict(LOCKUPS[a.lang])
    if a.tagline:
        lk["tag"] = a.tagline

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    n = int(round(a.duration * a.fps))
    tmp = Path(tempfile.mkdtemp(prefix="beehaviour_intro_"))
    try:
        for i in range(n):
            t = i / a.fps
            fr = draw_frame(t, a.width * a.ss, a.height * a.ss, a.duration, lk)
            fr = fr.resize((a.width, a.height), Image.LANCZOS)
            fr.save(tmp / f"{i:05d}.png")
            if i % 30 == 0:
                print(f"  frame {i}/{n}", flush=True)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(a.fps),
             "-i", str(tmp / "%05d.png"), "-c:v", "libx264", "-preset", "slow",
             "-crf", "16", "-pix_fmt", "yuv420p", str(out)], check=True)
        if a.poster:
            still = draw_frame(a.duration - 1.2, a.width * a.ss,
                               a.height * a.ss, a.duration, lk)
            still.resize((a.width, a.height), Image.LANCZOS).save(
                out.with_suffix(".png"))
            print(out.with_suffix(".png"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(out)


if __name__ == "__main__":
    main()
