# -*- coding: utf-8 -*-
"""Hoja de contactos de encuadres del plano general, con render de visor (rapido)."""
import bpy, os, math, time
from math import radians as rad

sc = bpy.context.scene
OUT = os.path.expanduser("~/Documents/beehaviour-2/blender/renders/angulos")
os.makedirs(OUT, exist_ok=True)

# (nombre, azimut, elevacion, distancia, focal)   azimut 0 = de frente; negativo = hacia la izquierda
ANGULOS = [
    ("a1_frontal_alto",     -20, 14, 2.40, 50),
    ("a2_frontal_bajo",     -18,  5, 2.20, 55),
    ("a3_tres_cuartos_izq", -42, 12, 2.50, 55),
    ("a4_tres_cuartos_der",  38, 12, 2.50, 55),
    ("a5_frontal",            0, 10, 2.30, 60),
    ("a6_picado",           -25, 30, 2.40, 45),
    ("a7_cercano_ancho",    -28,  9, 1.50, 28),
    ("a8_lateral",          -70, 10, 2.40, 60),
]
OBJETIVO = (-0.05, -0.10, 0.50)


def vista_previa(w=900, h=600):
    # sombreado de material en el render de visor; si la build no lo admite, solido
    try:
        sc.display.shading.type = 'MATERIAL'
    except TypeError:
        sc.display.shading.type = 'SOLID'
        sc.display.shading.light = 'STUDIO'
        sc.display.shading.color_type = 'MATERIAL'
        sc.display.shading.show_shadows = True
    sc.render.resolution_x, sc.render.resolution_y = w, h
    viz(False)
    hechos = []
    for nombre, az, el, dist, lente in ANGULOS:
        t0 = time.time()
        a, e = rad(az), rad(el)
        loc = (OBJETIVO[0] + dist * math.cos(e) * math.sin(a),
               OBJETIVO[1] - dist * math.cos(e) * math.cos(a),
               OBJETIVO[2] + dist * math.sin(e))
        cam = bpy.data.objects.get("Cam_Previa")
        if cam is None:
            cam = bpy.data.objects.new("Cam_Previa", bpy.data.cameras.new("Cam_Previa"))
            sc.collection.objects.link(cam)
            aim(cam, OBJETIVO, "Cam_Previa_Target")
        cam.data.lens = lente
        cam.data.dof.use_dof = False
        cam.location = loc
        sc.camera = cam
        sc.render.filepath = os.path.join(OUT, nombre)
        bpy.ops.render.opengl(write_still=True, view_context=False)
        hechos.append((nombre, round(time.time() - t0, 2)))
    viz(True)
    return hechos


def vista_color(w=900, h=600, muestras=32):
    """Los mismos encuadres con EEVEE, que si usa la GPU. ~15 s cada uno.

    Ojo: EEVEE aproxima la refraccion, asi que el metacrilato del visor y la tapa de
    la caja no se veran como en Cycles. Para decidir encuadre da igual.
    """
    prev_motor = sc.render.engine
    sc.render.engine = 'BLENDER_EEVEE'
    if hasattr(sc, 'eevee') and hasattr(sc.eevee, 'taa_render_samples'):
        sc.eevee.taa_render_samples = muestras
    sc.render.resolution_x, sc.render.resolution_y = w, h
    viz(False)
    cam = bpy.data.objects.get("Cam_Previa")
    if cam is None:
        cam = bpy.data.objects.new("Cam_Previa", bpy.data.cameras.new("Cam_Previa"))
        sc.collection.objects.link(cam)
        aim(cam, OBJETIVO, "Cam_Previa_Target")
    hechos = []
    for nombre, az, el, dist, lente in ANGULOS:
        t0 = time.time()
        a, e = rad(az), rad(el)
        cam.location = (OBJETIVO[0] + dist * math.cos(e) * math.sin(a),
                        OBJETIVO[1] - dist * math.cos(e) * math.cos(a),
                        OBJETIVO[2] + dist * math.sin(e))
        cam.data.lens = lente
        cam.data.dof.use_dof = False
        sc.camera = cam
        sc.render.filepath = os.path.join(OUT, "color_" + nombre)
        bpy.ops.render.render(write_still=True)
        hechos.append((nombre, round(time.time() - t0, 1)))
        print("   ", nombre, hechos[-1][1], "s", flush=True)
    viz(True)
    sc.render.engine = prev_motor
    return hechos


print("bh_angulos cargado:", len(ANGULOS), "encuadres")
