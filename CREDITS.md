# Credits and licences

## Code

All the code in this repository (`src/`, `box/`, `blender/`, the scripts at the
root) is under the **GNU AGPL-3.0**, full text in [LICENSE](LICENSE).

The licence is imposed by a dependency: the detection pipeline uses
[Ultralytics](https://github.com/ultralytics/ultralytics) YOLO11, which is
AGPL-3.0. The weights in `models/bee11n.pt` were trained with that library and
are a derivative work of it. Anyone wanting to use this in a closed commercial
product needs an Ultralytics Enterprise licence.

## Data, videos and images derived from the dataset

> Sledevic, Tomyslav (2024), **Labeled dataset for bee detection and direction
> estimation on beehive landing boards**, V6, Mendeley Data.
> DOI: [10.17632/8gb9r2yhfc.6](https://doi.org/10.17632/8gb9r2yhfc.6)
> Vilnius Gediminas Technical University (VILNIUS TECH).
> Licence: **CC BY 4.0**.

Under that licence, with attribution, this repository redistributes material
derived from the dataset:

| Path | What it is |
|---|---|
| `dataset-sample/images/`, `dataset-sample/labels/` | 14 labelled frames from the validation split, 2-3 per hive |
| `dataset-sample/zones/` | The 3 entrance polygons of the test videos |
| `media/entrada_cenital_muestra.mp4` | 15 s of `20230711b-fan.mp4`, rescaled to 1280 px |
| `media/*_conteo.mp4` | 20 s of each test video, with the pipeline's annotations overlaid |
| `docs/conteo.jpg`, `docs/conteo_densa.jpg` | Frames from the annotated videos |
| `out/*.csv`, `out/*_dets.npz`, `out/*_actividad.png` | Measurements and detections computed over the videos |

The full dataset (7.8 GB) is not redistributed: download it from the DOI above.

## Models

- `models/bee11n.pt` — YOLO11n fine-tuned on the dataset above. AGPL-3.0, for the
  reason given further up.
- `yolo11n.pt` (Ultralytics' COCO base weights) is not versioned; the library
  downloads it itself the first time you train.

## 3D mock-up

`blender/` builds the scene from code. The assets it downloads come from
[Poly Haven](https://polyhaven.com) and are **CC0**, so they impose no
conditions:

- HDRI `kloppenheim_05`
- Textures `sparse_grass`, `coated_pine`, `metal_plate`

They are not versioned (`blender/assets/` is in `.gitignore`); the scripts fetch
them.

## Libraries

| Library | Licence |
|---|---|
| Ultralytics YOLO11 | AGPL-3.0 |
| PyTorch, torchvision | BSD-3-Clause |
| OpenCV | Apache-2.0 |
| NumPy, SciPy, Matplotlib | BSD-3-Clause |
| Pillow | MIT-CMU |
| DejaVu Sans Mono (the video's typeface) | DejaVu licence (Bitstream Vera style) |
| Socket.IO (client, in `box/assets/libs/`) | MIT |
| FastAPI, and the Arduino App Lab bricks | MIT / per Arduino |
