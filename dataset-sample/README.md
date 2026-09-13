# Dataset sample

A handful of files from the Mendeley dataset, so you can see the format and try
the scripts without downloading 7.8 GB. **It is not enough to train on**: it is
14 frames.

```
images/   14 JPEG frames at 640x360, 2-3 per hive, from the validation split
labels/   their labels in YOLO format: `0 cx cy w h`, normalised, class 0 = bee
zones/    the landing-board polygon for each of the 3 test videos
```

The hives present here (`20230609a`, `20230609c`, `20230609d`, `20230609e`,
`20230711c`) are the training and validation ones. The three from the test videos
(`20230609b`, `20230711a`, `20230711b`) are deliberately absent: those are the
ones used for evaluation, and the model has never seen them.

## The zones

`zones/entrance_zone_<video>.txt` holds a four-corner polygon in 1920x1080
coordinates:

```
polygon = np.array([[245, 482], [1621, 482], [1617, 750], [255, 754]])
```

That is the landing board. Its top edge, the one facing the hive, is the entrance
line the counting uses. `beecount.py --zone` reads it and rescales it to the frame
size, so the entrance never has to be tuned by hand per camera.

## Full dataset

<https://doi.org/10.17632/8gb9r2yhfc.6> — CC BY 4.0. See [../CREDITS.md](../CREDITS.md)
for the citation.

Once downloaded, `src/build_dataset.py --src "<dataset>/detection"` assembles the
whole YOLO dataset, splitting by hive.
