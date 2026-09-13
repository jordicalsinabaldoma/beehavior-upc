# -*- coding: utf-8 -*-
"""Colmenar de fondo por instanciacion + postproduccion en el compositor."""
import bpy
from math import radians as rad

sc = bpy.context.scene

# ------------------------------------------------- colmenas de fondo
# Instanciar una coleccion no duplica geometria: dos colmenas mas salen casi gratis.
PREF_COLMENA = ('Cria_', 'Alza_', 'Entretapa', 'Techo_', 'Suelo_Colmena', 'Tabla_',
                'Listón_', 'Reductor_', 'Cabezal_', 'Panal_', 'Pata_', 'Travesano_')
ref = bpy.data.collections.get("Colmena_Ref") or bpy.data.collections.new("Colmena_Ref")
for o in bpy.data.objects:
    if o.type == 'MESH' and o.name.startswith(PREF_COLMENA) and o.name not in ref.objects:
        ref.objects.link(o)        # sigue viviendo en su coleccion original: no se duplica

FONDO = [((3.75, 3.45, 0.005), rad(21)), ((-2.70, 3.40, 0.002), rad(-16)),
         ((5.40, 4.60, 0.004), rad(38)), ((-5.10, 5.30, 0.003), rad(9))]
for i, (loc, rz) in enumerate(FONDO):
    e = bpy.data.objects.new(f"Colmena_Fondo_{i}", None)
    e.instance_type = 'COLLECTION'
    e.instance_collection = ref
    e.location = loc
    e.rotation_euler = (0, 0, rz)
    e.empty_display_size = 0.1
    sc.collection.objects.link(e)

# ------------------------------------------------------- compositor
# Blender 5 reemplazo scene.node_tree por un grupo de nodos cuyas propiedades pasaron
# a ser sockets. El grupo no recibe el render por su entrada y devolvia blanco, asi que
# la postproduccion (halo, vineteado, aberracion) se hace fuera, en post.py.
sc.use_nodes = False
if hasattr(sc, 'compositing_node_group'):
    sc.compositing_node_group = None

print("bh_post: colmenar de fondo +", len(FONDO), "instancias (post fuera de Blender)")
