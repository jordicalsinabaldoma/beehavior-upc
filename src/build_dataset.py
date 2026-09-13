#!/usr/bin/env python3
"""
Build a YOLO dataset from the Mendeley bee-detection folders.

Split by HIVE, not by frame: the hives that appear in the three test videos
(20230609b, 20230711a, 20230711b) are left out entirely, so detection and
counting are evaluated on colonies the model has never seen.
"""
import argparse
import random
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / ("Labeled dataset for bee detection and direction "
                       "estimation on beehive landing boards") / "detection"

# hives used by the three tracking videos -> held out from training
TEST_HIVES = {"20230609b", "20230711a", "20230711b"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "data" / "yolo_bees"))
    ap.add_argument("--step", type=int, default=2,
                    help="keep 1 of every N labeled frames (consecutive frames are near-identical)")
    ap.add_argument("--val-frac", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    for sub in ("images/train", "images/val", "labels/train", "labels/val"):
        (out / sub).mkdir(parents=True)

    rng = random.Random(args.seed)
    kept, skipped_hives, n_boxes = 0, [], 0
    counts = {"train": 0, "val": 0}

    for hive_dir in sorted(SRC.glob("_bee_*")):
        hive = hive_dir.name.replace("_bee_", "")
        if hive in TEST_HIVES:
            skipped_hives.append(hive)
            continue
        labels = sorted(p for p in (hive_dir / "labels").glob("*.txt")
                        if p.name != "classes.txt")
        labels = labels[::args.step]
        for lp in labels:
            ip = hive_dir / "images" / (lp.stem + ".jpg")
            if not ip.exists():
                continue
            body = lp.read_text().strip()
            if not body:
                continue                       # skip empty label files
            split = "val" if rng.random() < args.val_frac else "train"
            # symlink images (they are ~900 KB each, no point copying 3 GB)
            (out / "images" / split / ip.name).symlink_to(ip.resolve())
            (out / "labels" / split / lp.name).write_text(body + "\n")
            n_boxes += len(body.split("\n"))
            counts[split] += 1
            kept += 1

    (out / "bees.yaml").write_text(
        f"path: {out.resolve()}\ntrain: images/train\nval: images/val\n\n"
        "names:\n  0: bee\n"
    )

    print(f"hives held out (test videos): {sorted(skipped_hives)}")
    print(f"frames kept: {kept}  (train {counts['train']}, val {counts['val']})")
    print(f"bee boxes:   {n_boxes}")
    print(f"yaml:        {out / 'bees.yaml'}")


if __name__ == "__main__":
    main()
