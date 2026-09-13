# Beehaviour monitoring station: the 3D scene

A Blender reconstruction of the physical build: a Langstroth hive with a
top-down camera over the entrance, a control box holding the SoC and the
microcontroller, and a chain of sensors (two PIRs and two thermometers) wired in
series.

## Rebuilding the scene

The scene is generated **entirely from scripts**, idempotently: every pass calls
`purge()` and rebuilds. Edit a `.py`, re-run `run.py`, and you have the new
scene. The `.blend` is the output, not the source. That is why it is not
versioned.

```bash
blender --background --python blender/run.py
```

| File | Contents |
|---|---|
| `bh_lib.py` | UV-less primitives (`box`, `tube`, `dome`, `cable`) and base materials |
| `bh_build.py` | hive, stand, mast, top-down camera and framing visualisation |
| `bh_electronics.py` | weatherproof box, PCB, PIR sensors, thermometers and the wiring bus |
| `bh_env.py` | textured PBR materials, terrain, grass and flowers (Geometry Nodes) |
| `bh_bees.py` | hexagonal comb and bee population |
| `bh_render.py` | HDRI world, lights, cameras, Cycles settings and collections |
| `bh_post.py` | background apiary by instancing |
| `bh_shots.py` | the final shot series and post-processing |
| `run.py` | runs everything in order, in one shared namespace |

## Working interactively

What is set up on the development machine:

| Piece | Where | Notes |
|---|---|---|
| Blender 5.2 LTS | flatpak `--user` | no sudo; **sandboxed: it cannot see `/tmp`**, use paths under `$HOME` |
| `uv` / `uvx` | `~/.local/bin` | |
| MCP `blender-mcp` | user scope in Claude Code | `claude mcp get blender` |
| BlenderMCP add-on | `~/.var/app/org.blender.Blender/config/blender/5.2/scripts/addons/` | enabled and saved in preferences |
| Launcher | `~/.local/bin/blender-mcp` | opens Blender and starts the server on `localhost:9876` |

Run `blender-mcp` to work. If you open Blender from the menu instead, start the
server by hand in the 3D viewport: `N` → **BlenderMCP** tab → *Connect to Claude*.

To rebuild and render against a running instance from outside Blender:

```bash
python3 -c "
import sys; sys.path.insert(0,'$HOME/.local/share/blender-mcp')
import bmcp
print(bmcp.run(open('blender/run.py').read(), timeout=600)['result'])
"
```

`bmcp.py` is a ~30-line bridge speaking the same socket the MCP server uses.

## Cameras

- **Cam_Hero**: wide three-quarter shot.
- **Cam_Cenital**, *the system's camera*: 38.9 mm at 0.50 m above the landing board,
  a 16:9 frame of 464 × 261 mm. This is the view that would feed `beetrack.py`.
- **Cam_Piquera**, **Cam_Visor**, **Cam_Detalle**: the entrance with bees, the
  internal sensors, and the electronics.

`viz(True/False)` turns the technical overlay (frustum and top-down plane) on and
off.

## Shot series

`bh_shots.correr()` generates all six into `renders/`. It takes a name filter to
redo only some: `correr(filtro={"05_electronica"})`.

| File | What it shows |
|---|---|
| `01_general.png` | the wide shot with the technical overlay (frustum + top-down plane) |
| `02_general_limpio.png` | the same shot without the overlay |
| `03_piquera_abejas.png` | the entrance, the landing board and the bees |
| `04_visor_sensores.png` | PIR, indoor thermometer and the series bus behind the window |
| `05_electronica.png` | the board with SoC, microcontroller and sensor terminal block |
| `06_vista_camara.png` | **what the system's camera sees**, 1920×1080 |

Downscaled copies of these live in [../docs/renders/](../docs/renders/); the
full-size PNGs are not versioned.

## Decisions that are not obvious

- **Cycles runs on CPU.** The integrated Radeon 680M is not supported by HIP. 12
  threads, with adaptive sampling and denoising to compensate.
- **No UVs anywhere.** The meshes are generated with `from_pydata`, which carries no
  unwrap. Textures are applied with **BOX projection** over object coordinates.
- **Grass with Geometry Nodes, not particles.** The classic particle system
  evaluates all 140,000 instances but **never reaches the render** in Blender 5.
- **Hexagonal comb from three waves summed at 0/60/120°.** Shearing a Voronoi does
  not work: it measures distances in its input space, so the cells come out as
  rhombi.
- **Frames mounted the "warm way"** (comb face towards the window). Mounted
  front-to-back you would only see their edge.
- **The denoiser needs albedo and normal.** Without the auxiliary passes,
  OpenImageDenoise smears flat, out-of-focus backgrounds: few samples and low
  contrast make it invent blotches. You can see it in the sky and the hills.
- **Do not light from behind glass.** The first version put a point light inside the
  weatherproof box: even hidden from the camera (`visible_camera = False`, which
  only affects the primary ray), reflected and refracted rays still see it and two
  white blowouts appear on the lid. The light goes outside, high and well off to
  the side, so the specular reflection falls outside the lens.
- **Post-processing outside the compositor.** In Blender 5 `scene.node_tree` was
  dropped in favour of `compositing_node_group`, which does not receive the render
  on its input. The glow, the vignette and the saturation are applied with numpy
  over the PNG, in `bh_shots.postpro`.

## External assets

HDRI and textures from [Poly Haven](https://polyhaven.com), **CC0**, in
`assets/`: `kloppenheim_05` (sky), `coated_pine` (wood), `sparse_grass` (ground),
`metal_plate` (sheet metal). They get packed inside the `.blend`. Neither
`assets/` nor the `.blend` files are versioned.

## Checkpoints

Locally, `beehaviour_estacion.blend` is the live file, and `_cp1`,
`_cp2_entorno`, `_cp3_colmenar` and the rest are intermediate save points in case
you need to go back. None of them are in the repository. Rebuild from the
scripts instead.
