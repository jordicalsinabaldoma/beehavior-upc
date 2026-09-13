# Créditos y licencias

## Código

Todo el código de este repositorio (`src/`, `box/`, `blender/`, los scripts de la
raíz) está bajo **GNU AGPL-3.0**, texto completo en [LICENSE](LICENSE).

La licencia viene impuesta por la dependencia: el pipeline de detección usa
[Ultralytics](https://github.com/ultralytics/ultralytics) YOLO11, que es
AGPL-3.0. Los pesos de `models/bee11n.pt` se entrenaron con esa librería y son un
trabajo derivado suyo. Quien quiera usar esto en un producto comercial cerrado
necesita una licencia Enterprise de Ultralytics.

## Datos, vídeos e imágenes derivadas del dataset

> Sledevic, Tomyslav (2024), **Labeled dataset for bee detection and direction
> estimation on beehive landing boards**, V6, Mendeley Data.
> DOI: [10.17632/8gb9r2yhfc.6](https://doi.org/10.17632/8gb9r2yhfc.6)
> Vilnius Gediminas Technical University (VILNIUS TECH).
> Licencia: **CC BY 4.0**.

Bajo esa licencia, con atribución, este repositorio redistribuye material
derivado del dataset:

| Ruta | Qué es |
|---|---|
| `dataset-sample/images/`, `dataset-sample/labels/` | 14 fotogramas etiquetados del split de validación, 2-3 por colmena |
| `dataset-sample/zones/` | Los 3 polígonos de piquera de los vídeos de prueba |
| `media/entrada_cenital_muestra.mp4` | 15 s de `20230711b-fan.mp4`, reescalado a 1280 px |
| `media/*_conteo.mp4` | 20 s de cada vídeo de prueba, con las anotaciones del pipeline superpuestas |
| `docs/conteo.jpg`, `docs/conteo_densa.jpg` | Fotogramas de los vídeos anotados |
| `out/*.csv`, `out/*_dets.npz`, `out/*_actividad.png` | Medidas y detecciones calculadas sobre los vídeos |

El dataset completo (7,8 GB) no se redistribuye: se descarga del DOI de arriba.

## Modelos

- `models/bee11n.pt` — YOLO11n afinado sobre el dataset anterior. AGPL-3.0, por
  lo dicho más arriba.
- `yolo11n.pt` (pesos base COCO de Ultralytics) no se versiona; la librería lo
  descarga sola la primera vez que se entrena.

## Maqueta 3D

`blender/` construye la escena por código. Los recursos que descarga son de
[Poly Haven](https://polyhaven.com) y están bajo **CC0**, así que no imponen
condiciones:

- HDRI `kloppenheim_05`
- Texturas `sparse_grass`, `coated_pine`, `metal_plate`

No se versionan (`blender/assets/` está en `.gitignore`); los scripts los bajan.

## Librerías

| Librería | Licencia |
|---|---|
| Ultralytics YOLO11 | AGPL-3.0 |
| PyTorch, torchvision | BSD-3-Clause |
| OpenCV | Apache-2.0 |
| NumPy, SciPy, Matplotlib | BSD-3-Clause |
| Pillow | MIT-CMU |
| DejaVu Sans Mono (la tipografía del vídeo) | Licencia DejaVu (tipo Bitstream Vera) |
| Socket.IO (cliente, en `box/assets/libs/`) | MIT |
| FastAPI, y los bricks de Arduino App Lab | MIT / según Arduino |
