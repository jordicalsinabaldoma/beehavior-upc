# -*- coding: utf-8 -*-
"""Serie final de renders + postproduccion. Se ejecuta tras run.py."""
import bpy, os, time
import numpy as np

sc = bpy.context.scene
OUT = os.path.expanduser("~/Documents/beehaviour-2/blender/renders")
os.makedirs(OUT, exist_ok=True)


def _box1(x, r, axis):
    n = x.shape[axis]
    pad = [(0, 0)] * x.ndim
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(x, pad, mode='edge'), axis=axis)
    s1 = [slice(None)] * x.ndim; s2 = [slice(None)] * x.ndim
    s1[axis] = slice(2 * r + 1, 2 * r + 1 + n)
    s2[axis] = slice(0, n)
    return (c[tuple(s1)] - c[tuple(s2)]) / (2 * r + 1)


def _desenfoque(x, r):
    """Tres pasadas de caja aproximan una gaussiana y evitan depender de scipy."""
    for _ in range(3):
        x = _box1(x, r, 0)
        x = _box1(x, r, 1)
    return x


def postpro(path, halo=0.22, umbral=0.72, vineteo=0.30, sat=1.05):
    """Halo en altas luces + vineteado + saturacion, sobre el PNG ya revelado.

    Se hace aqui porque el compositor de Blender 5 no devuelve el render por la
    entrada del grupo de nodos, y el python del sistema no tiene numpy ni PIL.
    """
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    a = buf.reshape(h, w, 4)
    rgb = a[:, :, :3].copy()

    r = max(6, w // 70)
    exceso = np.clip(rgb.max(axis=2) - umbral, 0.0, None)[:, :, None]
    rgb += _desenfoque(rgb * exceso, r) * halo

    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    d = np.sqrt(((xx - cx) / cx) ** 2 + ((yy - cy) / cy) ** 2) / np.sqrt(2.0)
    rgb *= (1.0 - vineteo * np.clip((d - 0.34) / 0.66, 0.0, 1.0) ** 2)[:, :, None]

    gris = rgb.mean(axis=2, keepdims=True)
    a[:, :, :3] = np.clip(gris + (rgb - gris) * sat, 0.0, 1.0)
    img.pixels.foreach_set(a.reshape(-1))
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)


sc.cycles.caustics_refractive = False
sc.cycles.caustics_reflective = False
sc.cycles.use_denoising = True
sc.cycles.use_adaptive_sampling = True

# Sin pasadas auxiliares, OpenImageDenoise embarra los fondos planos y desenfocados
# (poca muestra + poco contraste = manchas). Albedo y normal se las dan.
for _attr, _val in (("denoising_input_passes", 'RGB_ALBEDO_NORMAL'),
                    ("denoising_prefilter", 'ACCURATE'),
                    ("denoising_quality", 'HIGH'),
                    ("denoising_use_gpu", False)):
    if hasattr(sc.cycles, _attr):
        try:
            setattr(sc.cycles, _attr, _val)
        except Exception as _e:
            print("denoise", _attr, _e)

# (camara, fichero, ancho, alto, muestras, overlay tecnico)
# (camara, fichero, ancho, alto, muestras, overlay tecnico)
# Resoluciones calibradas al presupuesto: Cycles va por CPU (12 hilos, la Radeon 680M
# integrada no esta soportada por HIP), asi que se apoya en muestreo adaptativo + denoise.
TOMAS = [
    ("Cam_Hero",    "01_general",          2000, 1333, 150, True),
    ("Cam_Hero",    "02_general_limpio",   2000, 1333, 150, False),
    ("Cam_Piquera", "03_piquera_abejas",   1800, 1200, 150, True),
    ("Cam_Visor",   "04_visor_sensores",   1800, 1200, 150, False),
    ("Cam_Detalle", "05_electronica",      1800, 1200, 160, False),
    ("Cam_Cenital", "06_vista_camara",     1920, 1080, 120, False),
    ("Cam_Picado",  "07_general_picado",   2000, 1333, 150, True),
]

def correr(filtro=None):
    hechos = []
    for cam, name, w, h, smp, overlay in TOMAS:
        if filtro and name not in filtro:
            continue
        t0 = time.time()
        viz(overlay)
        luz = bpy.data.objects.get("Luz_Caja")      # fill local, solo para el detalle
        if luz:
            luz.hide_render = (name != "05_electronica")
        sc.camera = bpy.data.objects[cam]
        sc.render.resolution_x, sc.render.resolution_y = w, h
        sc.cycles.samples = smp
        sc.cycles.adaptive_threshold = 0.013 if cam in ('Cam_Hero', 'Cam_Picado') else 0.018
        sc.render.filepath = os.path.join(OUT, name)
        bpy.ops.render.render(write_still=True)
        postpro(sc.render.filepath + ".png")
        dt = round(time.time() - t0, 1)
        hechos.append((name, dt))
        print(f"  {name}.png  {w}x{h}  {smp}spp  {dt}s", flush=True)
    viz(True)
    return hechos

print("bh_shots cargado:", len(TOMAS), "tomas definidas")
