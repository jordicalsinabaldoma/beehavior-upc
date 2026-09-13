# Beehaviour — notas técnicas de la PoC

Para el diseño no técnico ver [DISEÑO.md](DISEÑO.md).

## Estructura

```
dataset-minimal/   3 vídeos del dataset de Mendeley (1080p, 50 fps, 2 min cada uno)
src/beetrack.py    detección por movimiento + tracking + conteo entrada/salida + intruso
out/               vídeos anotados (*_track.mp4) y estadísticas por segundo (*.csv)
.venv/             entorno Python (opencv-python-headless, numpy, scipy)
```

## Ejecutar

```bash
.venv/bin/python src/beetrack.py dataset-minimal/20230609b-def.mp4 \
    --line 0.44 --roi-below 0.30 --skip 2 \
    -o out/20230609b-def_track.mp4 --csv out/20230609b-def.csv --show-mask
```

Parámetros usados por vídeo (posición de la ranura y zona de interés):

| vídeo | `--line` | `--roi-below` |
|---|---|---|
| 20230609b-def | 0.44 | 0.30 |
| 20230711a-fan | 0.22 | 0.65 |
| 20230711b-fan | 0.26 | 0.65 |

`--line` es la altura de la ranura de entrada como fracción del alto del frame. Por encima de la línea es "dentro de la colmena". `--roi-below` y `--roi-above` delimitan la franja donde se buscan abejas, para ignorar la hierba al viento. `--skip 2` procesa a 25 fps.

Los mp4 que escribe OpenCV van en mp4v. Para reproducirlos en navegador o móvil se reconvierten:

```bash
ffmpeg -i out/x_track_raw.mp4 -c:v libx264 -crf 22 -pix_fmt yuv420p out/x_track.mp4
```

## Cómo funciona (sin modelo entrenado)

1. Reescalado a 960 px de ancho y desenfoque suave.
2. Sustracción de fondo MOG2 con detección de sombras. Las sombras se descartan. La tasa de aprendizaje es baja para que una abeja recién posada siga siendo "primer plano" unos segundos.
3. Manchas filtradas por área relativa al frame, por relación de aspecto (elimina briznas de hierba) y por densidad de la mancha.
4. Tracking por asignación húngara sobre distancia de centroides con predicción de velocidad constante. Un track se confirma con 3 detecciones y sobrevive 0,8 s sin detección.
5. Conteo con tres reglas, cada track cuenta como mucho una vez:
   - A: cruce explícito de la línea (abajo a arriba = entra, arriba a abajo = sale).
   - B: track que nace en la zona de la ranura y se aleja hacia abajo = sale.
   - C: track que empezó claramente fuera, se movió hacia la ranura y desapareció en ella = entra.
6. Intruso candidato: mancha con área mayor que 4 veces la mediana de las abejas de la escena, mantenida 1 s. El umbral es relativo, así que se autocalibra a la distancia de la cámara.
7. Salida: vídeo con cajas, IDs, estelas, línea y panel de contadores; CSV por segundo con abejas en movimiento, acumulados de entradas y salidas, eventos de intruso y área mediana.

## Resultados en los tres vídeos (2 min cada uno)

| vídeo | entradas | salidas | abejas en movimiento (media / máx por frame) | intrusos |
|---|---|---|---|---|
| 20230609b-def | 132 | 19 | 4,2 / 7,8 | 0 |
| 20230711a-fan | 49 | 62 | 10,9 / 20,0 | 2 (falsos, grupos de abejas) |
| 20230711b-fan | 284 | 71 | 12,0 / 25,5 | 0 |

Velocidad en portátil: unos 65 fps a 960x540. En el Arduino UNO Q habrá que medir, pero el algoritmo es ligero.

No hay verdad de referencia para estas cifras. El dataset completo de Mendeley trae trayectorias anotadas que servirían para medir el error del conteo.

## Limitaciones observadas

- Una abeja que se queda quieta más de unos segundos se funde con el fondo y deja de detectarse. Al volver a moverse nace un ID nuevo. Esto fragmenta tracks e infla el conteo cuando hay muchas abejas paradas en la piquera.
- Dos abejas pegadas se detectan como una sola mancha. Con abejas peleando o abanicando en grupo puede saltar el aviso de intruso.
- La zona de interés y la altura de la línea se fijan a mano por cámara. El dataset de Mendeley incluye anotaciones de las esquinas de la tabla de vuelo, que permitirían autocalibrar esto.
- Con sol fuerte las sombras de abejas en vuelo se suprimen bien, pero no al cien por cien.

## Siguientes pasos posibles

- Medir precisión del conteo contra las trayectorias anotadas del dataset completo.
- Sustituir o complementar la detección por movimiento con un YOLO nano entrenado con las 7.200 imágenes etiquetadas de Mendeley. El resto del pipeline no cambia.
- Ejecutar en el Arduino UNO Q con la cámara real y medir fps.
- Integrar Modulino Thermo y Movement y la pantalla local de consulta.
