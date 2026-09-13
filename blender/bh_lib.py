# -*- coding: utf-8 -*-
"""Helpers de construccion y libreria de materiales para la escena Beehaviour."""
import bpy, math, mathutils

TAU = math.pi * 2

# ---------------------------------------------------------------- utilidades

def purge():
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.curves,
                 bpy.data.materials, bpy.data.lights, bpy.data.cameras,
                 bpy.data.node_groups, bpy.data.texts):
        for item in list(coll):
            try:
                coll.remove(item, do_unlink=True)
            except Exception:
                pass


def link(obj, collection=None):
    (collection or bpy.context.scene.collection).objects.link(obj)
    return obj


def bevel(obj, width=0.0015, segments=2, angle=40.0):
    m = obj.modifiers.new("Bevel", 'BEVEL')
    m.width = width
    m.segments = segments
    m.limit_method = 'ANGLE'
    m.angle_limit = math.radians(angle)
    m.harden_normals = True
    return obj


def smooth(obj, angle=35.0):
    for p in obj.data.polygons:
        p.use_smooth = True
    m = obj.modifiers.new("Smooth by Angle", 'WEIGHTED_NORMAL')
    m.keep_sharp = True
    return obj


def assign(obj, mat):
    if mat is not None:
        obj.data.materials.append(mat)
    return obj

# ---------------------------------------------------------------- primitivas

def box(name, size, loc=(0, 0, 0), rot=(0, 0, 0), mat=None, bev=0.0015, seg=2):
    sx, sy, sz = (s / 2.0 for s in size)
    verts = [(-sx, -sy, -sz), (sx, -sy, -sz), (sx, sy, -sz), (-sx, sy, -sz),
             (-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz)]
    faces = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1),
             (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    o = link(bpy.data.objects.new(name, me))
    o.location, o.rotation_euler = loc, rot
    assign(o, mat)
    if bev:
        bevel(o, bev, seg)
    return o


def tube(name, r, h, loc=(0, 0, 0), rot=(0, 0, 0), mat=None, n=48, r2=None, caps=True):
    """Cilindro / cono a lo largo de Z, centrado en el origen local."""
    r2 = r if r2 is None else r2
    verts, faces = [], []
    for i in range(n):
        a = TAU * i / n
        verts.append((math.cos(a) * r, math.sin(a) * r, -h / 2.0))
    for i in range(n):
        a = TAU * i / n
        verts.append((math.cos(a) * r2, math.sin(a) * r2, h / 2.0))
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, j + n, i + n))
    if caps:
        faces.append(tuple(range(n - 1, -1, -1)))
        faces.append(tuple(range(n, 2 * n)))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    o = link(bpy.data.objects.new(name, me))
    o.location, o.rotation_euler = loc, rot
    assign(o, mat)
    smooth(o)
    return o


def dome(name, rx, ry, rz, loc=(0, 0, 0), rot=(0, 0, 0), mat=None, seg=24, rings=8):
    """Media elipsoide (cupula) abierta hacia -Z."""
    verts, faces = [], []
    for ri in range(rings + 1):
        phi = (math.pi / 2.0) * ri / rings
        z, rr = math.cos(phi), math.sin(phi)
        for i in range(seg):
            a = TAU * i / seg
            verts.append((math.cos(a) * rr * rx, math.sin(a) * rr * ry, z * rz))
    for ri in range(rings):
        for i in range(seg):
            j = (i + 1) % seg
            a0, b0 = ri * seg + i, ri * seg + j
            a1, b1 = (ri + 1) * seg + i, (ri + 1) * seg + j
            faces.append((a0, b0, b1, a1))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    o = link(bpy.data.objects.new(name, me))
    o.location, o.rotation_euler = loc, rot
    assign(o, mat)
    smooth(o)
    return o


def cable(name, pts, r=0.0025, mat=None, res=5):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    sp = cu.splines.new('BEZIER')
    sp.bezier_points.add(len(pts) - 1)
    for bp, p in zip(sp.bezier_points, pts):
        bp.co = mathutils.Vector(p)
        bp.handle_left_type = bp.handle_right_type = 'AUTO'
    cu.bevel_depth = r
    cu.bevel_resolution = res
    cu.resolution_u = 18
    o = link(bpy.data.objects.new(name, cu))
    if mat:
        o.data.materials.append(mat)
    return o

# ---------------------------------------------------------------- materiales

def _bsdf(mat):
    for n in mat.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            return n
    return None


def _set(node, key, val):
    """Asigna un socket tolerando los renombrados entre versiones de Blender."""
    alias = {
        'Emission':  ('Emission Color', 'Emission'),
        'Specular':  ('Specular IOR Level', 'Specular'),
        'Transmission': ('Transmission Weight', 'Transmission'),
        'Clearcoat': ('Coat Weight', 'Clearcoat'),
        'Sheen':     ('Sheen Weight', 'Sheen'),
    }
    for k in alias.get(key, (key,)):
        if k in node.inputs:
            node.inputs[k].default_value = val
            return True
    return False


def pbr(name, color, metallic=0.0, rough=0.5, **kw):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = _bsdf(m)
    _set(b, 'Base Color', (*color, 1.0) if len(color) == 3 else color)
    _set(b, 'Metallic', metallic)
    _set(b, 'Roughness', rough)
    for k, v in kw.items():
        _set(b, k.replace('_', ' ').title(), v)
    return m


def emissive(name, color, strength=1.0, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = _bsdf(m)
    _set(b, 'Base Color', (*color, 1.0))
    _set(b, 'Emission', (*color, 1.0))
    _set(b, 'Emission Strength', strength)
    _set(b, 'Roughness', 0.4)
    if alpha < 1.0:
        _set(b, 'Alpha', alpha)
        m.blend_method = 'BLEND' if hasattr(m, 'blend_method') else m.blend_method
    return m


def wood(name, c_light, c_dark, scale=6.0, grain=(0.11, 7.0, 7.0), bump=0.12, rough=0.46):
    """Madera procedural: ruido estirado a lo largo de X = veta creible, sin UVs."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = _bsdf(m)
    coord = nt.nodes.new('ShaderNodeTexCoord')
    mapn = nt.nodes.new('ShaderNodeMapping')
    mapn.inputs['Scale'].default_value = grain          # aplasta X -> vetas largas
    veta = nt.nodes.new('ShaderNodeTexNoise')
    veta.inputs['Scale'].default_value = scale
    veta.inputs['Detail'].default_value = 9.0
    veta.inputs['Roughness'].default_value = 0.56
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.interpolation = 'EASE'
    ramp.color_ramp.elements[0].color = (*c_dark, 1.0)
    ramp.color_ramp.elements[1].color = (*c_light, 1.0)
    ramp.color_ramp.elements[0].position = 0.44
    ramp.color_ramp.elements[1].position = 0.59
    # poro fino, rompe la uniformidad y alimenta el relieve
    poro = nt.nodes.new('ShaderNodeTexNoise')
    poro.inputs['Scale'].default_value = 160.0
    poro.inputs['Detail'].default_value = 5.0
    mixr = nt.nodes.new('ShaderNodeMixRGB')
    mixr.blend_type = 'OVERLAY'
    mixr.inputs['Fac'].default_value = 0.10
    # rugosidad variable: la madera no refleja igual en toda la superficie
    rramp = nt.nodes.new('ShaderNodeValToRGB')
    rramp.color_ramp.elements[0].color = (rough - 0.10,) * 3 + (1.0,)
    rramp.color_ramp.elements[1].color = (min(rough + 0.14, 1.0),) * 3 + (1.0,)
    bmp = nt.nodes.new('ShaderNodeBump')
    bmp.inputs['Strength'].default_value = bump
    L = nt.links.new
    L(coord.outputs['Object'], mapn.inputs['Vector'])
    L(mapn.outputs['Vector'], veta.inputs['Vector'])
    L(coord.outputs['Object'], poro.inputs['Vector'])
    L(veta.outputs['Fac'], ramp.inputs['Fac'])
    L(ramp.outputs['Color'], mixr.inputs['Color1'])
    L(poro.outputs['Color'], mixr.inputs['Color2'])
    L(mixr.outputs['Color'], b.inputs['Base Color'])
    L(veta.outputs['Fac'], rramp.inputs['Fac'])
    L(rramp.outputs['Color'], b.inputs['Roughness'])
    L(poro.outputs['Fac'], bmp.inputs['Height'])
    L(bmp.outputs['Normal'], b.inputs['Normal'])
    return m


def glass(name, color, rough=0.06, transmission=1.0, ior=1.49):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = _bsdf(m)
    _set(b, 'Base Color', (*color, 1.0))
    _set(b, 'Roughness', rough)
    _set(b, 'Transmission', transmission)
    _set(b, 'IOR', ior)
    return m

print("bh_lib cargado")
