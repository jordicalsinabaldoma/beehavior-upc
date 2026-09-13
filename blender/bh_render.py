# -*- coding: utf-8 -*-
"""Mundo HDRI, camaras, ajustes de render y organizacion en colecciones."""
import bpy, math, os
from math import radians as rad

scene = bpy.context.scene

# ------------------------------------------------------------------- mundo
HDRI_PATH = os.path.expanduser("~/Documents/beehaviour-2/blender/assets/kloppenheim_05_4k.hdr")
hdri = bpy.data.images.load(HDRI_PATH, check_existing=True) if os.path.exists(HDRI_PATH) else None
w = bpy.data.worlds.get("Mundo") or bpy.data.worlds.new("Mundo")
scene.world = w
w.use_nodes = True
wn = w.node_tree
wn.nodes.clear()
out = wn.nodes.new('ShaderNodeOutputWorld')
bg = wn.nodes.new('ShaderNodeBackground')
bg.inputs['Strength'].default_value = 1.0   # el HDRI solo aporta ambiente y reflejos
wn.links.new(bg.outputs['Background'], out.inputs['Surface'])
if hdri:
    env = wn.nodes.new('ShaderNodeTexEnvironment')
    env.image = hdri
    mp = wn.nodes.new('ShaderNodeMapping')
    mp.inputs['Rotation'].default_value = (0, 0, rad(196))   # gira el cielo para encuadrar nubes
    tc = wn.nodes.new('ShaderNodeTexCoord')
    wn.links.new(tc.outputs['Generated'], mp.inputs['Vector'])
    wn.links.new(mp.outputs['Vector'], env.inputs['Vector'])
    wn.links.new(env.outputs['Color'], bg.inputs['Color'])
    print("HDRI en uso:", hdri.name)
else:
    bg.inputs['Color'].default_value = (0.35, 0.45, 0.62, 1)
    print("AVISO: sin HDRI, fondo plano")

def aim(obj, target, name):
    e = link(bpy.data.objects.new(name, None))
    e.location = target
    e.empty_display_size = 0.05
    c = obj.constraints.new('TRACK_TO')
    c.target = e
    c.track_axis = 'TRACK_NEGATIVE_Z'
    c.up_axis = 'UP_Y'
    return e

# sol: luz principal, sombras nitidas y direccion clara
sl = bpy.data.lights.new("Sol", 'SUN')
sl.energy = 1.5
sl.angle = rad(1.6)
sl.color = (1.0, 0.945, 0.872)
slo = link(bpy.data.objects.new("Sol", sl))
slo.rotation_euler = (rad(54), 0, rad(-74))       # lateral alta izq: sombras visibles a la derecha

# relleno frio en el lado de sombra
fl = bpy.data.lights.new("Relleno", 'AREA')
fl.energy, fl.size, fl.color = 42.0, 2.6, (0.70, 0.79, 1.0)
flo = link(bpy.data.objects.new("Relleno", fl))
flo.location = (2.5, -1.9, 1.4)
flo.rotation_euler = (rad(66), 0, rad(124))

# practicos tenues: sin ellos el interior de la colmena y la caja salen negros
il = bpy.data.lights.new("Interior_Colmena", 'AREA')
il.energy, il.color = 0.72, (1.0, 0.93, 0.82)
il.shape, il.size, il.size_y = 'RECTANGLE', 0.42, 0.045
ilo = link(bpy.data.objects.new("Interior_Colmena", il))
ilo.location = (0.0, -0.150, 0.6695)
ilo.rotation_euler = (0, 0, 0)                    # tira cenital: lame los cuadros hacia abajo

il2 = bpy.data.lights.new("Interior_Colmena_Fondo", 'POINT')
il2.energy, il2.shadow_soft_size, il2.color = 0.55, 0.09, (1.0, 0.90, 0.76)
il2o = link(bpy.data.objects.new("Interior_Colmena_Fondo", il2))
il2o.location = (0.0, 0.02, 0.600)

# Fotografiar a traves de un cristal: la luz NO puede ir detras de la tapa. Aunque se
# oculte a camara, los rayos reflejados y refractados siguen viendola y salen dos
# reventones blancos. Va fuera, alta y muy lateral, para que su reflejo especular
# caiga hacia abajo y no entre en el objetivo.
el_ = bpy.data.lights.new("Luz_Caja", 'AREA')
el_.energy, el_.size, el_.color = 34.0, 0.30, (0.94, 0.96, 1.0)
elo = link(bpy.data.objects.new("Luz_Caja", el_))
elo.location = (EX - 0.243, EY - 0.397, EZ + 0.265)
aim(elo, (EX, EY - 0.02, EZ), "Luz_Caja_Target")

# ninguna de estas luces debe verse: solo iluminan, no aparecen en el encuadre
for _l in (flo, ilo, il2o, elo):
    _l.visible_camera = False

# ----------------------------------------------------------------- camaras
def make_cam(name, loc, target=None, lens=50.0, fstop=None, rot=None):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.02
    co = link(bpy.data.objects.new(name, cd))
    co.location = loc
    if rot:
        co.rotation_euler = rot
    tgt = aim(co, target, name + "_Target") if target else None
    if fstop:
        cd.dof.use_dof = True
        cd.dof.aperture_fstop = fstop
        if tgt:
            cd.dof.focus_object = tgt
        else:
            cd.dof.focus_distance = loc[2] - 0.45
    return co

# encuadres elegidos sobre la hoja de contactos:
# a4 = tres cuartos derecha, el mastil no cruza por delante de la colmena
# a6 = picado, el unico que explica de un vistazo que mira la camara
cam_hero = make_cam("Cam_Hero", (1.456, -2.027, 1.02), (-0.05, -0.10, 0.50), 55.0, 5.6)
cam_pic  = make_cam("Cam_Picado", (-0.928, -1.984, 1.7), (-0.05, -0.10, 0.50), 45.0, 6.3)
cam_top  = make_cam("Cam_Cenital", (CAM_X, CAM_Y, CAM_Z - 0.014), None, CAM_LENS, None, rot=(0, 0, 0))
cam_det  = make_cam("Cam_Detalle", (EX - 0.22, EY - 0.58, EZ + 0.13), (EX, EY - 0.016, EZ), 70.0, 10.0)
cam_piq  = make_cam("Cam_Piquera", (-0.26, -0.94, 0.60), (0.0, -0.30, 0.452), 75.0, 7.0)
cam_vis  = make_cam("Cam_Visor", (-0.24, -1.02, 0.72), (-0.02, -0.19, 0.615), 90.0, 4.0)
scene.camera = cam_hero

# ------------------------------------------------------------ ajustes render
scene.render.engine = 'CYCLES'
try:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.refresh_devices()
    picked = None
    for ctype in ('OPTIX', 'CUDA', 'HIP', 'ONEAPI'):
        try:
            prefs.compute_device_type = ctype
            devs = [d for d in prefs.devices if d.type == ctype]
            if devs:
                for d in prefs.devices:
                    d.use = (d.type == ctype)
                picked = (ctype, [d.name for d in devs])
                break
        except Exception:
            continue
    scene.cycles.device = 'GPU' if picked else 'CPU'
    print("Dispositivo Cycles:", picked or "CPU")
except Exception as e:
    print("Cycles prefs:", e)

scene.cycles.samples = 300
scene.cycles.use_denoising = True
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.008
scene.cycles.max_bounces = 16
scene.cycles.transmission_bounces = 16
scene.cycles.transparent_max_bounces = 16
scene.cycles.caustics_refractive = True
scene.render.film_transparent = False
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_depth = '8'
try:
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
except Exception as e:
    print("view transform:", e)

# -------------------------------------------------------------- colecciones
GROUPS = {
    'Colmena':       ('Cria_', 'Alza_', 'Panal_', 'Cabezal_', 'Techo_', 'Entretapa', 'Suelo_', 'Tabla_', 'Listón_', 'Reductor_'),
    'Soporte':       ('Pata_', 'Travesano_', 'Mastil', 'Brazo', 'Codo', 'Perno_', 'Visera_'),
    'Electronica':   ('Caja_', 'PCB', 'SoC_', 'MCU_', 'Blindaje', 'Regleta', 'Tira_', 'Pin_', 'USB_', 'Condensador', 'LED_', 'Antena', 'Prensaestopa'),
    'Sensores':      ('Termo_', 'Abrigo_', 'Camara_', 'Pasamuros', 'Modulo_'),
    'Cableado':      ('Bus_', 'Brida_'),
    'Visualizacion': ('Frustum', 'Plano_Cenital', 'Borde_Cenital'),
    'Entorno':       ('Terreno',),
}
for gname, prefixes in GROUPS.items():
    c = bpy.data.collections.get(gname) or bpy.data.collections.new(gname)
    if gname not in {x.name for x in scene.collection.children}:
        scene.collection.children.link(c)
    for o in list(scene.collection.objects):
        if o.name.startswith(prefixes):
            scene.collection.objects.unlink(o)
            c.objects.link(o)

def viz(on):
    """Muestra u oculta el overlay tecnico (frustum + plano cenital)."""
    c = bpy.data.collections.get('Visualizacion')
    if c:
        for o in c.objects:
            o.hide_render = not on
            o.hide_viewport = not on      # el render de visor mira esta, no hide_render
    # las luces practicas solo tienen sentido con el corte tecnico
    return on


OUT = os.path.expanduser("~/Documents/beehaviour-2/blender/renders")

def shot(cam, filename, w=2400, h=1350, samples=None):
    scene.camera = bpy.data.objects[cam]
    scene.render.resolution_x, scene.render.resolution_y = w, h
    if samples:
        scene.cycles.samples = samples
    scene.render.filepath = os.path.join(OUT, filename)
    bpy.ops.render.render(write_still=True)
    return scene.render.filepath + ".png"

print("bh_render listo. Objetos en escena:", len(bpy.data.objects))
