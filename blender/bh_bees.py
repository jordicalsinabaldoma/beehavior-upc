# -*- coding: utf-8 -*-
"""Panal con celdillas y poblacion de abejas en la piquera."""
import bpy, math, random
from math import radians as rad

random.seed(21)

# ------------------------------------------------------- panal con celdillas
def mat_panal(name, celda=0.0054):
    """Panal hexagonal autentico.

    Cizallar un Voronoi no sirve: mide distancias en su espacio de entrada, asi que
    las celdas siguen siendo cuadradas y al deformarlas salen rombos. La suma de tres
    ondas planas a 0/60/120 grados si tiene simetria hexagonal: sus maximos forman
    una malla triangular y, por tanto, celdas hexagonales.
    """
    freq = math.tau / (celda * math.sqrt(3) / 2.0)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = _bsdf(m)
    L = nt.links.new
    coord = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    L(coord.outputs['Object'], sep.inputs['Vector'])

    cosenos = []
    for grados in (0.0, 60.0, 120.0):
        a = math.radians(grados)
        mz = nt.nodes.new('ShaderNodeMath'); mz.operation = 'MULTIPLY'
        mz.inputs[1].default_value = math.sin(a)
        L(sep.outputs['Z'], mz.inputs[0])
        u = nt.nodes.new('ShaderNodeMath'); u.operation = 'MULTIPLY_ADD'
        u.inputs[1].default_value = math.cos(a)
        L(sep.outputs['X'], u.inputs[0])
        L(mz.outputs['Value'], u.inputs[2])
        esc = nt.nodes.new('ShaderNodeMath'); esc.operation = 'MULTIPLY'
        esc.inputs[1].default_value = freq
        L(u.outputs['Value'], esc.inputs[0])
        co = nt.nodes.new('ShaderNodeMath'); co.operation = 'COSINE'
        L(esc.outputs['Value'], co.inputs[0])
        cosenos.append(co)

    s1 = nt.nodes.new('ShaderNodeMath'); s1.operation = 'ADD'
    L(cosenos[0].outputs['Value'], s1.inputs[0])
    L(cosenos[1].outputs['Value'], s1.inputs[1])
    s2 = nt.nodes.new('ShaderNodeMath'); s2.operation = 'ADD'
    L(s1.outputs['Value'], s2.inputs[0])
    L(cosenos[2].outputs['Value'], s2.inputs[1])
    norm = nt.nodes.new('ShaderNodeMapRange')       # -1.5..3 -> 0..1
    norm.inputs['From Min'].default_value = -1.5
    norm.inputs['From Max'].default_value = 3.0
    L(s2.outputs['Value'], norm.inputs['Value'])

    # 0 = pared de cera, 1 = fondo de celdilla
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.interpolation = 'B_SPLINE'
    ramp.color_ramp.elements[0].position = 0.05
    ramp.color_ramp.elements[0].color = (0.792, 0.598, 0.268, 1)
    ramp.color_ramp.elements[1].position = 0.74
    ramp.color_ramp.elements[1].color = (0.132, 0.070, 0.020, 1)
    L(norm.outputs['Result'], ramp.inputs['Fac'])

    # miel operculada arriba, cria abajo, con manchas irregulares
    nz = nt.nodes.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 5.5
    nz.inputs['Detail'].default_value = 7.0
    L(coord.outputs['Object'], nz.inputs['Vector'])
    zr = nt.nodes.new('ShaderNodeMapRange')
    zr.inputs['From Min'].default_value = -0.10
    zr.inputs['From Max'].default_value = 0.09
    L(sep.outputs['Z'], zr.inputs['Value'])
    mezc = nt.nodes.new('ShaderNodeMath'); mezc.operation = 'MULTIPLY_ADD'
    mezc.inputs[1].default_value = 0.92
    mezc.inputs[2].default_value = 0.10
    L(nz.outputs['Fac'], mezc.inputs[0])
    suma = nt.nodes.new('ShaderNodeMath'); suma.operation = 'ADD'
    L(zr.outputs['Result'], suma.inputs[0])
    L(mezc.outputs['Value'], suma.inputs[1])
    zona = nt.nodes.new('ShaderNodeMixRGB')
    zona.inputs['Color1'].default_value = (0.362, 0.206, 0.072, 1)   # cria
    zona.inputs['Color2'].default_value = (0.910, 0.732, 0.352, 1)   # miel
    L(suma.outputs['Value'], zona.inputs['Fac'])

    tinte = nt.nodes.new('ShaderNodeMixRGB'); tinte.blend_type = 'MULTIPLY'
    tinte.inputs['Fac'].default_value = 0.88
    L(ramp.outputs['Color'], tinte.inputs['Color1'])
    L(zona.outputs['Color'], tinte.inputs['Color2'])
    L(tinte.outputs['Color'], b.inputs['Base Color'])

    # relieve: la pared sobresale, el fondo se hunde
    inv = nt.nodes.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'
    inv.inputs[0].default_value = 1.0
    L(norm.outputs['Result'], inv.inputs[1])
    bmp = nt.nodes.new('ShaderNodeBump')
    bmp.inputs['Strength'].default_value = 0.85
    bmp.inputs['Distance'].default_value = 0.0035
    L(inv.outputs['Value'], bmp.inputs['Height'])
    L(bmp.outputs['Normal'], b.inputs['Normal'])
    _set(b, 'Roughness', 0.54)
    _set(b, 'Transmission', 0.08)
    _set(b, 'IOR', 1.44)
    return m


panal = mat_panal("Cera de Panal")
for o in bpy.data.objects:
    if o.type == 'MESH' and o.name.startswith('Panal_'):
        o.data.materials.clear()
        o.data.materials.append(panal)

# --------------------------------------------------------------- esferoide
def esfera(name, rx, ry, rz, loc=(0, 0, 0), rot=(0, 0, 0), mat=None, seg=16, rings=10):
    verts, faces = [], []
    for ri in range(rings + 1):
        phi = math.pi * ri / rings
        z, rr = math.cos(phi), math.sin(phi)
        for i in range(seg):
            a = math.tau * i / seg
            verts.append((math.cos(a) * rr * rx, math.sin(a) * rr * ry, z * rz))
    for ri in range(rings):
        for i in range(seg):
            j = (i + 1) % seg
            faces.append((ri * seg + i, ri * seg + j, (ri + 1) * seg + j, (ri + 1) * seg + i))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    o = link(bpy.data.objects.new(name, me))
    o.location, o.rotation_euler = loc, rot
    if mat:
        o.data.materials.append(mat)
    smooth(o)
    return o

# ------------------------------------------------------ materiales de abeja
m_abdomen = bpy.data.materials.new("Abdomen Abeja")
m_abdomen.use_nodes = True
_nt = m_abdomen.node_tree
_b = _bsdf(m_abdomen)
_co = _nt.nodes.new('ShaderNodeTexCoord')
_sep = _nt.nodes.new('ShaderNodeSeparateXYZ')
_wav = _nt.nodes.new('ShaderNodeMath'); _wav.operation = 'MULTIPLY'; _wav.inputs[1].default_value = 520.0
_snd = _nt.nodes.new('ShaderNodeMath'); _snd.operation = 'SINE'
_rmp = _nt.nodes.new('ShaderNodeValToRGB')
_rmp.color_ramp.interpolation = 'CONSTANT'
_rmp.color_ramp.elements[0].color = (0.032, 0.024, 0.018, 1)      # banda oscura
_rmp.color_ramp.elements[1].position = 0.48
_rmp.color_ramp.elements[1].color = (0.582, 0.332, 0.052, 1)      # banda ambar
_nt.links.new(_co.outputs['Object'], _sep.inputs['Vector'])
_nt.links.new(_sep.outputs['Z'], _wav.inputs[0])
_nt.links.new(_wav.outputs['Value'], _snd.inputs[0])
_nt.links.new(_snd.outputs['Value'], _rmp.inputs['Fac'])
_nt.links.new(_rmp.outputs['Color'], _b.inputs['Base Color'])
_set(_b, 'Roughness', 0.62)

m_torax = pbr("Torax Abeja", (0.238, 0.162, 0.078), 0.0, 0.78)
m_cabeza = pbr("Cabeza Abeja", (0.035, 0.028, 0.022), 0.0, 0.45)
m_ala = bpy.data.materials.new("Ala")
m_ala.use_nodes = True
_set(_bsdf(m_ala), 'Base Color', (0.92, 0.94, 0.96, 1.0))
_set(_bsdf(m_ala), 'Roughness', 0.10)
_set(_bsdf(m_ala), 'Transmission', 0.92)
_set(_bsdf(m_ala), 'IOR', 1.33)

# ------------------------------------------------------------------ abeja
def abeja(idx, loc, yaw=0.0, pitch=0.0, volando=False, escala=1.0):
    """Abeja de ~13 mm: a este tamano manda la silueta y el rayado, no el detalle."""
    partes = []
    S = 0.0130 * escala
    partes.append(esfera(f"Abeja{idx}_Abdomen", S * 0.26, S * 0.26, S * 0.42,
                         (0, S * 0.34, 0), (rad(90), 0, 0), m_abdomen, 14, 9))
    partes.append(esfera(f"Abeja{idx}_Torax", S * 0.25, S * 0.27, S * 0.25,
                         (0, -S * 0.10, S * 0.02), (0, 0, 0), m_torax, 14, 9))
    partes.append(esfera(f"Abeja{idx}_Cabeza", S * 0.18, S * 0.17, S * 0.18,
                         (0, -S * 0.40, S * 0.02), (0, 0, 0), m_cabeza, 12, 8))
    for sx in (-1, 1):
        ala = esfera(f"Abeja{idx}_Ala_{sx}", S * 0.40, S * 0.15, S * 0.030,
                     (sx * S * 0.34, S * 0.02, S * 0.16),
                     (0, 0, rad(sx * (18 if volando else 34))), m_ala, 12, 6)
        partes.append(ala)
    for sx in (-1, 1):
        for k, off in enumerate((-0.18, 0.02, 0.22)):
            partes.append(tube(f"Abeja{idx}_Pata_{sx}_{k}", S * 0.022, S * 0.30,
                               (sx * S * 0.22, S * off, -S * 0.16),
                               (rad(24 * (1 if volando else -1)), rad(sx * 34), 0),
                               m_cabeza, n=6))
    raiz = link(bpy.data.objects.new(f"Abeja{idx}", None))
    raiz.empty_display_size = 0.01
    raiz.location = loc
    raiz.rotation_euler = (pitch, 0, yaw)
    for pz in partes:
        pz.parent = raiz
        pz.matrix_parent_inverse.identity()
    return raiz

# ----------------------------------------------- colocacion en la piquera
# posadas: la cota sale de la geometria real de la tabla, que esta inclinada
POSADAS = [
    (-0.145, -0.268, 0.9),  (-0.060, -0.300, 2.3), (0.028, -0.252, 0.4),
    (0.112, -0.286, 3.6),   (0.186, -0.244, 1.7),  (-0.212, -0.240, 5.4),
    (0.068, -0.352, 2.9),   (-0.108, -0.336, 4.4), (-0.020, -0.232, 1.2),
    (0.148, -0.330, 5.9),   (-0.176, -0.300, 2.6), (0.092, -0.228, 0.2),
]
for i, (x, y, yaw) in enumerate(POSADAS):
    abeja(i, (x, y, altura_tabla(y) + 0.0042), yaw=yaw, escala=random.uniform(0.9, 1.1))

VUELO = [
    (-0.26, -0.42, 0.60), (-0.05, -0.46, 0.70), (0.20, -0.40, 0.55),
    (0.33, -0.32, 0.78), (-0.19, -0.36, 0.86), (0.08, -0.49, 0.92),
    (-0.36, -0.28, 0.50), (0.26, -0.47, 0.64), (0.02, -0.38, 0.50),
    (-0.13, -0.44, 0.62), (0.15, -0.35, 0.66),
]
for i, (x, y, z) in enumerate(VUELO):
    abeja(100 + i, (x, y, z), yaw=random.uniform(0, math.tau),
          pitch=rad(random.uniform(-26, 26)), volando=True,
          escala=random.uniform(0.85, 1.05))

print("bh_bees: panal con celdillas +", len(POSADAS) + len(VUELO), "abejas")
