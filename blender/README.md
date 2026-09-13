# Estación de monitorización Beehaviour — escena 3D

Reconstrucción en Blender del montaje físico: colmena Langstroth con cámara cenital
sobre la piquera, caja de control con SoC y microcontrolador, y una cadena de sensores
(dos PIR y dos termómetros) conectados en serie.

## Qué hay montado en la máquina

| Pieza | Dónde | Notas |
|---|---|---|
| Blender 5.2 LTS | flatpak `--user` | sin sudo; **sandbox: no ve `/tmp`**, usa rutas bajo `$HOME` |
| `uv` / `uvx` | `~/.local/bin` | |
| MCP `blender-mcp` | scope usuario en Claude Code | `claude mcp get blender` |
| Addon BlenderMCP | `~/.var/app/org.blender.Blender/config/blender/5.2/scripts/addons/` | activado y guardado en preferencias |
| Lanzador | `~/.local/bin/blender-mcp` | abre Blender y arranca el servidor en `localhost:9876` |

Para trabajar: ejecuta `blender-mcp`. Si abres Blender desde el menú, activa el servidor
a mano en el visor 3D con `N` → pestaña **BlenderMCP** → *Connect to Claude*.

## Estructura de la escena

La escena se genera **por completo desde scripts**, de forma idempotente: cada pasada
llama a `purge()` y reconstruye. Editas un `.py`, reejecutas `run.py` y tienes la escena
nueva. El `.blend` es el resultado, no la fuente.

| Fichero | Contenido |
|---|---|
| `bh_lib.py` | primitivas sin UVs (`box`, `tube`, `dome`, `cable`) y materiales base |
| `bh_build.py` | colmena, soporte, mástil, cámara cenital y visualización del encuadre |
| `bh_electronics.py` | caja estanca, PCB, sensores PIR, termómetros y bus de cableado |
| `bh_env.py` | materiales PBR texturizados, terreno, césped y flores (Geometry Nodes) |
| `bh_bees.py` | panal hexagonal y población de abejas |
| `bh_render.py` | mundo HDRI, luces, cámaras, ajustes de Cycles y colecciones |
| `bh_post.py` | colmenar de fondo por instanciación |
| `bh_shots.py` | serie de tomas finales y postproducción |
| `run.py` | ejecuta todo en orden en un espacio de nombres común |

Reconstruir y renderizar desde fuera de Blender:

```bash
python3 -c "
import sys; sys.path.insert(0,'$HOME/.local/share/blender-mcp')
import bmcp
print(bmcp.run(open('$HOME/Documents/beehaviour-2/blender/run.py').read(), timeout=600)['result'])
"
```

`bmcp.py` es un puente de ~30 líneas que habla el mismo socket que usa el MCP.

## Cámaras

- **Cam_Hero** — plano general 3/4.
- **Cam_Cenital** — *la cámara del sistema*: 38,9 mm a 0,50 m sobre la tabla de vuelo,
  encuadre 16:9 de 464 × 261 mm. Es la vista que alimentaría `beetrack.py`.
- **Cam_Piquera**, **Cam_Visor**, **Cam_Detalle** — piquera con abejas, sensores
  interiores y electrónica.

`viz(True/False)` enciende o apaga el overlay técnico (frustum y plano cenital).

## Serie de tomas

`bh_shots.correr()` genera las seis en `renders/`. Acepta un filtro por nombre para
rehacer solo algunas: `correr(filtro={"05_electronica"})`.

| Fichero | Qué muestra |
|---|---|
| `01_general.png` | plano general con overlay técnico (frustum + plano cenital) |
| `02_general_limpio.png` | el mismo plano sin overlay |
| `03_piquera_abejas.png` | piquera, tabla de vuelo y abejas |
| `04_visor_sensores.png` | PIR, termómetro interior y bus en serie tras el visor |
| `05_electronica.png` | placa con SoC, microcontrolador y regleta de sensores |
| `06_vista_camara.png` | **lo que ve la cámara del sistema**, 1920×1080 |

## Decisiones que no son obvias

- **Cycles va por CPU.** La Radeon 680M integrada no está soportada por HIP. 12 hilos,
  con muestreo adaptativo y denoise para compensar.
- **Nada de UVs.** Las mallas se generan con `from_pydata`, que no trae despliegue. Las
  texturas se aplican con **proyección BOX** sobre coordenadas de objeto.
- **Césped con Geometry Nodes, no partículas.** El sistema de partículas clásico
  evalúa las 140 000 instancias pero **no llega al render** en Blender 5.
- **Panal hexagonal por suma de tres ondas a 0/60/120°.** Cizallar un Voronoi no vale:
  mide distancias en su espacio de entrada, así que las celdas salen en rombo.
- **Cuadros en "sentido cálido"** (cara del panal hacia el visor). Montados de frente a
  fondo solo se vería su canto.
- **El denoiser necesita albedo y normal.** Sin las pasadas auxiliares, OpenImageDenoise
  embarra los fondos planos y desenfocados: pocas muestras y poco contraste le hacen
  inventar manchas. Se ve en el cielo y las colinas.
- **No se ilumina detrás de un cristal.** La primera versión puso un punto de luz dentro
  de la caja estanca: aunque se oculte a cámara (`visible_camera = False`, que solo afecta
  al rayo primario), los rayos reflejados y refractados siguen viéndola y salen dos
  reventones blancos sobre la tapa. La luz va fuera, alta y muy lateral, para que el
  reflejo especular caiga fuera del objetivo.
- **Postproducción fuera del compositor.** En Blender 5 `scene.node_tree` desapareció en
  favor de `compositing_node_group`, que no recibe el render por su entrada. El halo,
  el viñeteado y la saturación se aplican con numpy sobre el PNG, en `bh_shots.postpro`.

## Recursos externos

HDRI y texturas de [Poly Haven](https://polyhaven.com), **CC0**, en `assets/`:
`kloppenheim_05` (cielo), `coated_pine` (madera), `sparse_grass` (suelo),
`metal_plate` (chapa). Van empaquetados dentro del `.blend`.

## Checkpoints

`beehaviour_estacion.blend` es el archivo vivo. Los `_cp1`, `_cp2_entorno` y
`_cp3_colmenar` son puntos de guardado intermedios por si hay que volver atrás.
