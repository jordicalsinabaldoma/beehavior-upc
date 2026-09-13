#!/usr/bin/env python3
"""
Build a single demo reel from the rendered dashboard videos:
title card -> quiet hive -> busy hive -> intruder alert -> results card.
"""
import argparse
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

C_BG = (26, 22, 18)
C_TEXT = (238, 238, 238)
C_DIM = (155, 155, 155)
C_ACC = (90, 200, 90)
FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_B = cv2.FONT_HERSHEY_DUPLEX


def card(size, lines, out):
    """lines: list of (text, scale, color, thickness, font, gap_after)"""
    W, H = size
    img = np.full((H, W, 3), C_BG, np.uint8)
    heights = []
    for s, sc, col, th, fn, gap in lines:
        (tw, tht), _ = cv2.getTextSize(s, fn, sc, th)
        heights.append(tht + gap)
    y = (H - sum(heights)) // 2
    for (s, sc, col, th, fn, gap), hh in zip(lines, heights):
        (tw, tht), _ = cv2.getTextSize(s, fn, sc, th)
        y += tht
        cv2.putText(img, s, ((W - tw) // 2, y), fn, sc, col, th, cv2.LINE_AA)
        y += gap
    cv2.rectangle(img, (0, H - 6), (W, H), (60, 52, 44), -1)
    cv2.imwrite(str(out), img)


def clip_from_png(png, seconds, size, fps, out):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(png),
                    "-t", str(seconds), "-r", str(fps),
                    "-vf", f"scale={size[0]}:{size[1]}",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                    "-pix_fmt", "yuv420p", str(out)], check=True)


def cut(src, start, dur, size, fps, out):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(start), "-t", str(dur),
                    "-i", str(src), "-r", str(fps),
                    "-vf", f"scale={size[0]}:{size[1]}",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                    "-pix_fmt", "yuv420p", str(out)], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="out/BEEHAVIOUR_demo.mp4")
    ap.add_argument("--fps", type=int, default=25)
    ap.add_argument("--tmp", default="/tmp/reel")
    args = ap.parse_args()

    tmp = Path(args.tmp)
    tmp.mkdir(parents=True, exist_ok=True)

    quiet = Path("out/20230609b-def_beehaviour.mp4")
    busy = Path("out/20230711b-fan_beehaviour.mp4")
    intr = Path("out/demo_intruder_beehaviour.mp4")
    for f in (quiet, busy):
        if not f.exists():
            sys.exit(f"falta {f}; ejecuta ./run_all.sh primero")

    cap = cv2.VideoCapture(str(quiet))
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    size = (W, H)

    parts = []

    card(size, [
        ("BEEHAVIOUR", 2.6, C_TEXT, 4, FONT_B, 26),
        ("guardian de colmena que funciona sin cobertura", 0.9, C_DIM, 2, FONT, 46),
        ("cuenta abejas  ·  detecta intrusos  ·  todo en el dispositivo", 0.75, C_ACC, 2, FONT, 0),
    ], tmp / "c0.png")
    clip_from_png(tmp / "c0.png", 3.5, size, args.fps, tmp / "p0.mp4")
    parts.append(tmp / "p0.mp4")

    card(size, [
        ("1 · COLMENA TRANQUILA", 1.6, C_TEXT, 3, FONT_B, 22),
        ("pocas abejas, se cuenta cada entrada y cada salida", 0.8, C_DIM, 2, FONT, 0),
    ], tmp / "c1.png")
    clip_from_png(tmp / "c1.png", 2.5, size, args.fps, tmp / "p1.mp4")
    parts.append(tmp / "p1.mp4")
    cut(quiet, 30, 22, size, args.fps, tmp / "p1v.mp4")
    parts.append(tmp / "p1v.mp4")

    card(size, [
        ("2 · COLMENA MUY ACTIVA", 1.6, C_TEXT, 3, FONT_B, 22),
        ("mas de 30 abejas a la vez en la tabla de vuelo", 0.8, C_DIM, 2, FONT, 0),
    ], tmp / "c2.png")
    clip_from_png(tmp / "c2.png", 2.5, size, args.fps, tmp / "p2.mp4")
    parts.append(tmp / "p2.mp4")
    cut(busy, 45, 22, size, args.fps, tmp / "p2v.mp4")
    parts.append(tmp / "p2v.mp4")

    if intr.exists():
        card(size, [
            ("3 · ALGO QUE NO ES UNA ABEJA", 1.5, C_TEXT, 3, FONT_B, 22),
            ("el sistema sabe como es una abeja y avisa de lo que no lo es", 0.78, C_DIM, 2, FONT, 18),
            ("(intruso simulado: el dataset no contiene avispones)", 0.62, (110, 110, 110), 1, FONT, 0),
        ], tmp / "c3.png")
        clip_from_png(tmp / "c3.png", 3.0, size, args.fps, tmp / "p3.mp4")
        parts.append(tmp / "p3.mp4")
        cut(intr, 8, 26, size, args.fps, tmp / "p3v.mp4")
        parts.append(tmp / "p3v.mp4")

    card(size, [
        ("MEDIDO CONTRA LA VERDAD DEL DATASET", 1.2, C_TEXT, 3, FONT_B, 30),
        ("deteccion de abejas      F1 0.82     (solo movimiento: 0.44)", 0.8, C_TEXT, 2, FONT, 18),
        ("abejas en la tabla       error medio por debajo del 10%", 0.8, C_TEXT, 2, FONT, 18),
        ("colmenas de prueba       nunca vistas en el entrenamiento", 0.8, C_ACC, 2, FONT, 30),
        ("40 ms por frame en portatil  ·  sin nube  ·  sin internet", 0.72, C_DIM, 2, FONT, 0),
    ], tmp / "c4.png")
    clip_from_png(tmp / "c4.png", 5.0, size, args.fps, tmp / "p4.mp4")
    parts.append(tmp / "p4.mp4")

    lst = tmp / "concat.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-c", "copy", args.out], check=True)
    print(f"{args.out}  ({len(parts)} tramos, {W}x{H})")


if __name__ == "__main__":
    main()
