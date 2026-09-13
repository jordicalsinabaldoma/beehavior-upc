# -*- coding: utf-8 -*-
"""Entorno: materiales con texturas PBR reales, cesped, flores y detalle de suelo."""
import bpy, os, math, random
from math import radians as rad

ASSETS = os.path.expanduser("~/Documents/beehaviour-2/blender/assets")
random.seed(7)

# ------------------------------------------------------------ material PBR
def pbr_tex(name, prefix, scale=1.0, ao_mix=0.65, bump=0.22, rough_mul=1.0,
            metallic=0.0, blend=0.30, tint=None, hsv=None, base_rgb=None):
    """Textura Poly Haven con proyeccion BOX sobre coordenadas de objeto.

    Proyectar en caja evita tener que desplegar UVs en mallas generadas por codigo.
    """
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = _bsdf(m)
    coord = nt.nodes.new('ShaderNodeTexCoord')
    mapn = nt.nodes.new('ShaderNodeMapping')
    mapn.inputs['Scale'].default_value = (scale, scale, scale)
    nt.links.new(coord.outputs['Object'], mapn.inputs['Vector'])

    def img(short, non_color=True):
        for ext in ("jpg", "png"):
            path = os.path.join(ASSETS, f"{prefix}_{short}.{ext}")
            if os.path.exists(path):
                n = nt.nodes.new('ShaderNodeTexImage')
                n.image = bpy.data.images.load(path, check_existing=True)
                n.projection = 'BOX'
                n.projection_blend = blend
                n.extension = 'REPEAT'
                if non_color:
                    n.image.colorspace_settings.name = 'Non-Color'
                nt.links.new(mapn.outputs['Vector'], n.inputs['Vector'])
                return n
        return None

    diff = img('diff', non_color=False)
    ao   = img('ao')
    rgh  = img('rough')
    nor  = img('nor')
    dsp  = img('disp')

    color_out = diff.outputs['Color'] if diff else None
    if diff and ao and ao_mix > 0:                       # el AO da profundidad a las juntas
        mx = nt.nodes.new('ShaderNodeMixRGB')
        mx.blend_type = 'MULTIPLY'
        mx.inputs['Fac'].default_value = ao_mix
        nt.links.new(diff.outputs['Color'], mx.inputs['Color1'])
        nt.links.new(ao.outputs['Color'], mx.inputs['Color2'])
        color_out = mx.outputs['Color']
    if color_out and tint:
        tn = nt.nodes.new('ShaderNodeMixRGB')
        tn.blend_type = 'COLOR'
        tn.inputs['Fac'].default_value = tint[3]
        nt.links.new(color_out, tn.inputs['Color1'])
        tn.inputs['Color2'].default_value = (*tint[:3], 1.0)
        color_out = tn.outputs['Color']
    if hsv and color_out:                                # corrige tono/saturacion/luminosidad
        hn = nt.nodes.new('ShaderNodeHueSaturation')
        hn.inputs['Hue'].default_value = hsv[0]
        hn.inputs['Saturation'].default_value = hsv[1]
        hn.inputs['Value'].default_value = hsv[2]
        nt.links.new(color_out, hn.inputs['Color'])
        color_out = hn.outputs['Color']
    if base_rgb is not None:                             # metales: color plano, relieve de los mapas
        _set(b, 'Base Color', (*base_rgb, 1.0))
    elif color_out:
        nt.links.new(color_out, b.inputs['Base Color'])

    if rgh:
        if rough_mul != 1.0:
            mm = nt.nodes.new('ShaderNodeMath')
            mm.operation = 'MULTIPLY'
            mm.inputs[1].default_value = rough_mul
            nt.links.new(rgh.outputs['Color'], mm.inputs[0])
            nt.links.new(mm.outputs['Value'], b.inputs['Roughness'])
        else:
            nt.links.new(rgh.outputs['Color'], b.inputs['Roughness'])
    _set(b, 'Metallic', metallic)

    normal_out = None
    if nor:
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nm.inputs['Strength'].default_value = 1.0
        nt.links.new(nor.outputs['Color'], nm.inputs['Color'])
        normal_out = nm.outputs['Normal']
    if dsp and bump > 0:
        bp = nt.nodes.new('ShaderNodeBump')
        bp.inputs['Strength'].default_value = bump
        nt.links.new(dsp.outputs['Color'], bp.inputs['Height'])
        if normal_out:
            nt.links.new(normal_out, bp.inputs['Normal'])
        normal_out = bp.outputs['Normal']
    if normal_out:
        nt.links.new(normal_out, b.inputs['Normal'])
    return m


def retex(prefixes, mat, exclude=()):
    n = 0
    for o in bpy.data.objects:
        if o.type != 'MESH' or not o.name.startswith(prefixes):
            continue
        if any(x in o.name for x in exclude):
            continue                                  # el visor no es madera
        o.data.materials.clear()
        o.data.materials.append(mat)
        n += 1
    return n

# ------------------------------------------------ reemplazo de materiales
MT = {}
MT['pino']  = pbr_tex("TEX Pino", "coated_pine", scale=1.6, ao_mix=0.45, bump=0.18,
                      rough_mul=1.15, hsv=(0.515, 0.62, 2.55))      # pino claro, no caoba
MT['pino2'] = pbr_tex("TEX Pino Envejecido", "coated_pine", scale=1.1, ao_mix=0.65, bump=0.30,
                      rough_mul=1.45, hsv=(0.508, 0.45, 1.85))      # soporte mas gris y mate
MT['chapa'] = pbr_tex("TEX Chapa Galvanizada", "metal_plate", scale=2.2, ao_mix=0.0, bump=0.14,
                      rough_mul=0.80, metallic=1.0, base_rgb=(0.596, 0.621, 0.638))
MT['tabla'] = pbr_tex("TEX Tabla Vuelo", "coated_pine", scale=1.9, ao_mix=0.30, bump=0.07,
                      rough_mul=1.9, hsv=(0.505, 0.20, 3.6))   # clara y mate: DISENO.md dice
                                                               # que asi se detecta mucho mejor
MT['suelo'] = pbr_tex("TEX Suelo Hierba", "sparse_grass", scale=0.42, ao_mix=0.55, bump=0.65,
                      hsv=(0.512, 0.90, 1.25))

retex(('Cria_', 'Alza_', 'Entretapa', 'Suelo_Colmena', 'Listón_',
       'Reductor_', 'Cabezal_', 'Techo_Faldon', 'Lateral_Cuadro_'), MT['pino'], exclude=('Metacrilato',))
retex(('Tabla_',), MT['tabla'])
retex(('Pata_', 'Travesano_'), MT['pino2'])
retex(('Techo_Chapa',), MT['chapa'])
retex(('Terreno',), MT['suelo'])

# ---------------------------------------------------- relieve real del suelo
terreno = bpy.data.objects['Terreno']
sub = terreno.modifiers.new("Subdiv", 'SUBSURF')
sub.subdivision_type = 'SIMPLE'
sub.levels = sub.render_levels = 6           # malla suficiente para ondular el terreno
dtex = bpy.data.textures.new("RelieveTerreno", 'CLOUDS')
dtex.noise_scale = 3.2
dsp = terreno.modifiers.new("Ondulacion", 'DISPLACE')
dsp.texture = dtex
dsp.strength = 0.085
dsp.mid_level = 0.5

# ------------------------------------------------------- brizna de cesped
def brizna(name, h=0.062, w=0.0040, segs=5, bend=0.50):
    verts, faces = [], []
    for i in range(segs + 1):
        t = i / segs
        z = h * t
        y = bend * h * t * t                      # la punta cae por su propio peso
        half = w * (1.0 - t) ** 0.75 / 2.0
        verts += [(-half, y, z), (half, y, z)]
    for i in range(segs):
        a = i * 2
        faces.append((a, a + 1, a + 3, a + 2))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    o = link(bpy.data.objects.new(name, me))
    o.location = (120, 120, 0)                    # fuera de encuadre: solo sirve de instancia
    smooth(o)
    return o


def mat_cesped(name, c_base, c_punta, var=0.22):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = _bsdf(m)
    info = nt.nodes.new('ShaderNodeObjectInfo')
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    # degradado de la base a la punta a lo largo de la brizna
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(geo.outputs['Position'], sep.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (*c_base, 1.0)
    ramp.color_ramp.elements[1].color = (*c_punta, 1.0)
    mapr = nt.nodes.new('ShaderNodeMapRange')
    mapr.inputs['From Min'].default_value = 0.0
    mapr.inputs['From Max'].default_value = 0.068
    nt.links.new(sep.outputs['Z'], mapr.inputs['Value'])
    nt.links.new(mapr.outputs['Result'], ramp.inputs['Fac'])
    # variacion de tono por brizna, para que no parezca moqueta
    hsv = nt.nodes.new('ShaderNodeHueSaturation')
    hsv.inputs['Saturation'].default_value = 1.0
    nt.links.new(ramp.outputs['Color'], hsv.inputs['Color'])
    mr2 = nt.nodes.new('ShaderNodeMapRange')
    mr2.inputs['To Min'].default_value = 1.0 - var
    mr2.inputs['To Max'].default_value = 1.0 + var
    nt.links.new(info.outputs['Random'], mr2.inputs['Value'])
    nt.links.new(mr2.outputs['Result'], hsv.inputs['Value'])
    nt.links.new(hsv.outputs['Color'], b.inputs['Base Color'])
    _set(b, 'Roughness', 0.62)
    # algo de translucidez: la hierba a contraluz no es opaca
    _set(b, 'Transmission', 0.14)
    _set(b, 'IOR', 1.33)
    return m


hoja = brizna("Brizna")
hoja.data.materials.append(mat_cesped("Cesped", (0.055, 0.115, 0.021), (0.212, 0.286, 0.072)))

# ------------------------------------------------------------ flor sencilla
def flor(name, r=0.010):
    verts, faces = [], []
    for i in range(5):
        a = math.tau * i / 5
        ca, sa = math.cos(a), math.sin(a)
        verts += [(ca * r * 0.25, sa * r * 0.25, 0.0),
                  (math.cos(a + 0.5) * r, math.sin(a + 0.5) * r, r * 0.22),
                  (math.cos(a - 0.5) * r, math.sin(a - 0.5) * r, r * 0.22)]
        faces.append((i * 3, i * 3 + 1, i * 3 + 2))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    o = link(bpy.data.objects.new(name, me))
    o.location = (124, 120, 0)
    return o


petalo = flor("Flor")
mflor = bpy.data.materials.new("Petalo")
mflor.use_nodes = True
_set(_bsdf(mflor), 'Base Color', (0.945, 0.932, 0.858, 1.0))
_set(_bsdf(mflor), 'Roughness', 0.55)
_set(_bsdf(mflor), 'Transmission', 0.20)
petalo.data.materials.append(mflor)

# ------------------------------------------------- dispersion (Geometry Nodes)
def _sock(node, name, which='inputs', kind=None):
    """Busca socket por nombre (y tipo): los indices del nodo Random Value
    cambian segun data_type, asi que no se puede acceder por posicion."""
    for sk in getattr(node, which):
        if sk.name == name and (kind is None or sk.type == kind):
            return sk
    return None


def plano(name, size, loc):
    sx, sy = size[0] / 2, size[1] / 2
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-sx, -sy, 0), (sx, -sy, 0), (sx, sy, 0), (-sx, sy, 0)], [], [(0, 1, 2, 3)])
    me.update()
    o = link(bpy.data.objects.new(name, me))
    o.location = loc
    return o


def scatter_gn(obj, name, inst, density, seed=0, s_min=0.72, s_max=1.34, tilt=0.22):
    """Siembra instancias sobre las caras del objeto. Sustituye al sistema de
    particulas clasico, que en Blender 5 ya no llega al render."""
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links.new
    gin, gout = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
    dist = N.new('GeometryNodeDistributePointsOnFaces')
    dist.distribute_method = 'RANDOM'
    _sock(dist, 'Density').default_value = density
    _sock(dist, 'Seed').default_value = seed
    oinfo = N.new('GeometryNodeObjectInfo')
    oinfo.inputs['Object'].default_value = inst
    iop = N.new('GeometryNodeInstanceOnPoints')
    rot = N.new('GeometryNodeRotateInstances')
    rot.inputs['Local Space'].default_value = True
    sca = N.new('GeometryNodeScaleInstances')

    rv = N.new('FunctionNodeRandomValue')          # giro aleatorio en Z + inclinacion
    rv.data_type = 'FLOAT_VECTOR'
    _sock(rv, 'Min', kind='VECTOR').default_value = (-tilt, -tilt, 0.0)
    _sock(rv, 'Max', kind='VECTOR').default_value = (tilt, tilt, math.tau)
    sk = _sock(rv, 'Seed')
    if sk:
        sk.default_value = seed + 11

    rs = N.new('FunctionNodeRandomValue')          # tamano aleatorio
    rs.data_type = 'FLOAT'
    _sock(rs, 'Min', kind='VALUE').default_value = s_min
    _sock(rs, 'Max', kind='VALUE').default_value = s_max
    sk = _sock(rs, 'Seed')
    if sk:
        sk.default_value = seed + 23

    L(gin.outputs[0], dist.inputs['Mesh'])
    L(dist.outputs['Points'], iop.inputs['Points'])
    L(dist.outputs['Rotation'], iop.inputs['Rotation'])
    L(oinfo.outputs['Geometry'], iop.inputs['Instance'])
    L(iop.outputs['Instances'], rot.inputs['Instances'])
    L(_sock(rv, 'Value', 'outputs', 'VECTOR'), rot.inputs['Rotation'])
    L(rot.outputs['Instances'], sca.inputs['Instances'])
    L(_sock(rs, 'Value', 'outputs', 'VALUE'), sca.inputs['Scale'])
    L(sca.outputs['Instances'], gout.inputs[0])

    m = obj.modifiers.new(name, 'NODES')
    m.node_group = ng
    return ng


emisor = plano("Cesped_Emisor", (7.6, 7.6), (0.10, 0.30, 0.0))
# el cesped debe seguir las ondulaciones del terreno: mismo subdiv + displace
es = emisor.modifiers.new("Subdiv", 'SUBSURF')
es.subdivision_type = 'SIMPLE'
es.levels = es.render_levels = 6
ed = emisor.modifiers.new("Ondulacion", 'DISPLACE')
ed.texture = dtex
ed.strength = 0.085
ed.mid_level = 0.5

scatter_gn(emisor, "Cesped", hoja, density=3400, seed=3, s_min=0.55, s_max=1.50, tilt=0.30)

emisor_f = plano("Flores_Emisor", (6.4, 6.4), (0.10, 0.30, 0.012))
fs = emisor_f.modifiers.new("Subdiv", 'SUBSURF')
fs.subdivision_type = 'SIMPLE'
fs.levels = fs.render_levels = 5
fd = emisor_f.modifiers.new("Ondulacion", 'DISPLACE')
fd.texture = dtex
fd.strength = 0.085
fd.mid_level = 0.5
scatter_gn(emisor_f, "Flores", petalo, density=26, seed=9, s_min=0.7, s_max=1.4, tilt=0.35)

print("bh_env: texturas y vegetacion listas")
