# Clips

Short, re-encoded excerpts. The full videos are not in the repo: the originals
are 128-205 MB each, above GitHub's 100 MB per-file limit, and the annotated
ones are 60-74 MB.

| File | What it is |
|---|---|
| `entrada_cenital_muestra.mp4` | 15 s of `20230711b-fan.mp4`, the pipeline's raw input |
| `20230609b-def_conteo.mp4` | 20 s of the quiet hive, annotated |
| `20230711a-fan_conteo.mp4` | 20 s of the busy hive: 25 bees on the board on average |
| `20230711b-fan_conteo.mp4` | 20 s of the hive with the most entries |

The annotated ones are regenerated at full resolution from the detections saved
in `out/*_dets.npz`, without running the detector again:

```bash
VIDEOS_DIR=/path/to/videos ./rerender.sh
```

Material derived from the Mendeley dataset, CC BY 4.0. See [../CREDITS.md](../CREDITS.md).
