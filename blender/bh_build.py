# -*- coding: utf-8 -*-
"""Geometria de la estacion de monitorizacion Beehaviour (unidades = metros)."""
import bpy, math
from math import radians as rad

# ------------------------------------------------------------------ medidas
BW, BD, WALL = 0.508, 0.416, 0.022      # Langstroth real
BX, BY = BW / 2, BD / 2
LEG_H = 0.42
BOARD_Z = 0.44                           # cara superior del suelo de la colmena
RIM = 0.019                              # alto de la piquera
BROOD_Z0 = BOARD_Z + RIM                 # 0.459
BROOD_H = 0.242
BROOD_Z1 = BROOD_Z0 + BROOD_H            # 0.701
SUPER_H = 0.159
SUPER_Z1 = BROOD_Z1 + SUPER_H            # 0.860
MAST_X, MAST_Y = -0.50, -0.30
CAM_X, CAM_Y = 0.0, -0.325
CAM_ALT = 0.30            # altura sobre la tabla de vuelo (DESIGN.md 3.1 y dataset Mendeley)
CAM_LENS = 24.0           # cubre 45 x 25 cm a esa altura: tabla entera + aire por delante
TABLA_Y, TABLA_D, TABLA_TILT = -0.322, 0.200, rad(-7)
TABLA_CZ = BOARD_Z - 0.002


def altura_tabla(y):
    """Cota de la cara superior de la tabla de vuelo en una Y dada (esta inclinada)."""
    import math as _m
    c, sn = _m.cos(TABLA_TILT), _m.sin(TABLA_TILT)
    dy = (y - TABLA_Y + 0.008 * sn) / c
    return TABLA_CZ + dy * sn + 0.008 * c


PLANE_Z = altura_tabla(CAM_Y)          # tabla justo bajo la camara
CAM_Z = PLANE_Z + CAM_ALT + 0.014      # cuerpo de la camara; el centro optico va 14 mm mas abajo
ARM_Z = CAM_Z + 0.077
MAST_H = ARM_Z + 0.028
HWX = CAM_ALT * 18.0 / CAM_LENS        # semiancho del encuadre sobre la tabla
HWY = HWX * 9.0 / 16.0

# limpia la escena por defecto (cubo/luz/camara) y todo lo de pasadas previas
purge()

# --------------------------------------------------------------- materiales
M = {}
M['pine']     = wood("Madera Pino", (0.641, 0.487, 0.298), (0.494, 0.347, 0.201), 5.0, (0.055, 30.0, 30.0), 0.055, 0.45)
M['pine_y']   = wood("Madera Pino Y", (0.641, 0.487, 0.298), (0.494, 0.347, 0.201), 5.0, (30.0, 0.055, 30.0), 0.055, 0.45)
M['pine_z']   = wood("Madera Pino Z", (0.641, 0.487, 0.298), (0.494, 0.347, 0.201), 5.0, (30.0, 30.0, 0.055), 0.055, 0.45)
M['pine_old'] = wood("Madera Envejecida", (0.416, 0.352, 0.268), (0.278, 0.222, 0.162), 4.5, (0.065, 26.0, 26.0), 0.085, 0.61)
M['pine_old_z'] = wood("Madera Envejecida Z", (0.416, 0.352, 0.268), (0.278, 0.222, 0.162), 4.5, (26.0, 26.0, 0.065), 0.085, 0.61)
M['pine_old_y'] = wood("Madera Envejecida Y", (0.416, 0.352, 0.268), (0.278, 0.222, 0.162), 4.5, (26.0, 0.065, 26.0), 0.085, 0.61)
M['galv']     = pbr("Chapa Galvanizada", (0.606, 0.627, 0.639), 1.0, 0.34)
M['alu']      = pbr("Aluminio Anodizado", (0.372, 0.392, 0.408), 1.0, 0.27)
M['steel']    = pbr("Acero Inox", (0.690, 0.702, 0.714), 1.0, 0.19)
M['abs']      = pbr("ABS Gris Oscuro", (0.048, 0.052, 0.058), 0.0, 0.42)
M['abs_mid']  = pbr("ABS Gris", (0.118, 0.126, 0.135), 0.0, 0.48)
M['white']    = pbr("Plastico Blanco", (0.842, 0.849, 0.855), 0.0, 0.38)
M['rubber']   = pbr("Goma Negra", (0.017, 0.017, 0.019), 0.0, 0.63)
M['pcb']      = pbr("PCB Verde", (0.021, 0.132, 0.060), 0.0, 0.38)
M['chip']     = pbr("Encapsulado", (0.026, 0.026, 0.030), 0.0, 0.36)
M['gold']     = pbr("Contactos Oro", (0.744, 0.552, 0.212), 1.0, 0.24)
M['wax']      = pbr("Cera de Panal", (0.628, 0.408, 0.118), 0.0, 0.55)
M['acrylic']  = glass("Metacrilato", (0.925, 0.948, 0.938), 0.010, 1.00, 1.49)
M['poly']     = glass("Policarbonato", (0.742, 0.772, 0.788), 0.016, 1.00, 1.52)
M['viz']      = emissive("Viz Cian", (0.086, 0.706, 0.804), 0.50, 0.017)
M['viz_edge'] = emissive("Viz Borde", (0.165, 0.878, 0.960), 7.0, 1.0)
M['led_g']    = emissive("LED Verde", (0.129, 0.925, 0.318), 3.2)
M['led_b']    = emissive("LED Azul", (0.180, 0.494, 0.984), 2.6)
M['lens']     = pbr("Optica", (0.012, 0.014, 0.020), 0.0, 0.05, coat_weight=1.0)
M['ir']       = emissive("LED IR", (0.612, 0.106, 0.106), 3.0)
M['ground']   = pbr("Terreno", (0.096, 0.112, 0.052), 0.0, 0.93)

OBJ = []
def reg(o):
    OBJ.append(o)
    return o

# ------------------------------------------------------------------- soporte
for sx in (-1, 1):
    for sy in (-1, 1):
        reg(box(f"Pata_{sx}_{sy}", (0.055, 0.055, LEG_H),
                (sx * (BX - 0.05), sy * (BY - 0.05), LEG_H / 2), mat=M['pine_old_z'], bev=0.002))
for sy in (-1, 1):
    reg(box(f"Travesano_X_{sy}", (BW - 0.03, 0.042, 0.034),
            (0, sy * (BY - 0.05), 0.392), mat=M['pine_old'], bev=0.002))
for sx in (-1, 1):
    reg(box(f"Travesano_Y_{sx}", (0.042, BD - 0.14, 0.034),
            (sx * (BX - 0.05), 0, 0.348), mat=M['pine_old_y'], bev=0.002))

# --------------------------------------------------------- suelo y piquera
reg(box("Suelo_Colmena", (BW + 0.04, BD + 0.04, 0.020), (0, 0, BOARD_Z - 0.010),
        mat=M['pine'], bev=0.002))
reg(box("Tabla_Vuelo", (BW - 0.01, TABLA_D, 0.016), (0, TABLA_Y, TABLA_CZ),
        rot=(TABLA_TILT, 0, 0), mat=M['pine'], bev=0.002))
for sx in (-1, 1):
    reg(box(f"Listón_Lateral_{sx}", (RIM, BD, RIM),
            (sx * (BX - RIM / 2), 0, BOARD_Z + RIM / 2), mat=M['pine'], bev=0.001))
reg(box("Listón_Trasero", (BW, RIM, RIM), (0, BY - RIM / 2, BOARD_Z + RIM / 2),
        mat=M['pine'], bev=0.001))
for sx in (-1, 1):
    reg(box(f"Reductor_Piquera_{sx}", (0.172, RIM, RIM),
            (sx * 0.148, -(BY - RIM / 2), BOARD_Z + RIM / 2), mat=M['pine'], bev=0.001))

# ------------------------------------- camara de cria (frente transparente)
BZC = BROOD_Z0 + BROOD_H / 2
reg(box("Cria_Frente_Metacrilato", (BW - 0.004, 0.008, BROOD_H - 0.004),
        (0, -(BY - WALL - 0.004), BZC), mat=M['acrylic'], bev=0.001))
for sx in (-1, 1):   # marco del visor
    reg(box(f"Cria_Marco_V_{sx}", (0.050, WALL, BROOD_H), (sx * (BX - 0.025), -(BY - WALL / 2), BZC),
            mat=M['pine_z'], bev=0.0015))
reg(box("Cria_Marco_H_1", (BW, WALL, 0.030), (0, -(BY - WALL / 2), BZC + BROOD_H / 2 - 0.015),
        mat=M['pine'], bev=0.0015))
reg(box("Cria_Marco_H_-1", (BW, WALL, 0.046), (0, -(BY - WALL / 2), BZC - BROOD_H / 2 + 0.023),
        mat=M['pine'], bev=0.0015))
reg(box("Cria_Trasera", (BW, WALL, BROOD_H), (0, BY - WALL / 2, BZC), mat=M['pine'], bev=0.0015))
for sx in (-1, 1):
    reg(box(f"Cria_Lateral_{sx}", (WALL, BD - 2 * WALL, BROOD_H),
            (sx * (BX - WALL / 2), 0, BZC), mat=M['pine_y'], bev=0.0015))
    reg(box(f"Cria_Asa_{sx}", (0.022, 0.30, 0.026), (sx * (BX + 0.011), 0, BZC + 0.072),
            mat=M['pine'], bev=0.002))

# cuadros de panal, montados "en sentido calido": la cara del panal mira al visor,
# asi por la ventana se ven las celdillas y no el canto del cuadro
NF, PITCH, Y0 = 8, 0.042, -0.112
for i in range(NF):
    y = Y0 + i * PITCH
    reg(box(f"Panal_{i}", (BW - 2 * WALL - 0.020, 0.026, 0.196), (0, y, BROOD_Z0 + 0.118),
            mat=M['wax'], bev=0.001))
    reg(box(f"Cabezal_{i}", (BW - 2 * WALL + 0.014, 0.036, 0.017), (0, y, BROOD_Z1 - 0.016),
            mat=M['pine'], bev=0.001))
    for sx in (-1, 1):   # lateral del cuadro
        reg(box(f"Lateral_Cuadro_{i}_{sx}", (0.014, 0.030, 0.188),
                (sx * (BW / 2 - WALL - 0.014), y, BROOD_Z0 + 0.112), mat=M['pine'], bev=0.001))

# -------------------------------------------------------------- alza (media)
SZC = BROOD_Z1 + SUPER_H / 2
for sx in (-1, 1):
    reg(box(f"Alza_Lateral_{sx}", (WALL, BD - 2 * WALL, SUPER_H), (sx * (BX - WALL / 2), 0, SZC),
            mat=M['pine_y'], bev=0.0015))
    reg(box(f"Alza_Asa_{sx}", (0.022, 0.30, 0.026), (sx * (BX + 0.011), 0, SZC), mat=M['pine'], bev=0.002))
for sy in (-1, 1):
    reg(box(f"Alza_Frontal_{sy}", (BW, WALL, SUPER_H), (0, sy * (BY - WALL / 2), SZC),
            mat=M['pine'], bev=0.0015))

# ------------------------------------------------------- entretapa y techo
reg(box("Entretapa", (BW, BD, 0.014), (0, 0, SUPER_Z1 + 0.007), mat=M['pine'], bev=0.0015))
LID_Z0, LID_H = SUPER_Z1 - 0.012, 0.086
LZC = LID_Z0 + LID_H / 2
for sy in (-1, 1):
    reg(box(f"Techo_Faldon_Y_{sy}", (BW + 0.044, 0.020, LID_H), (0, sy * (BY + 0.012), LZC),
            mat=M['pine'], bev=0.002))
for sx in (-1, 1):
    reg(box(f"Techo_Faldon_X_{sx}", (0.020, BD - 0.016, LID_H), (sx * (BX + 0.012), 0, LZC),
            mat=M['pine_y'], bev=0.002))
reg(box("Techo_Chapa", (BW + 0.050, BD + 0.030, 0.007), (0, 0, LID_Z0 + LID_H + 0.0035),
        mat=M['galv'], bev=0.0018, seg=3))

# ------------------------------------------------------------------- mastil
reg(tube("Mastil", 0.021, MAST_H, (MAST_X, MAST_Y, MAST_H / 2), mat=M['alu'], n=40))
reg(box("Mastil_Base", (0.155, 0.155, 0.014), (MAST_X, MAST_Y, 0.007), mat=M['steel'], bev=0.002))
for dx, dy in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
    reg(tube(f"Perno_{dx}_{dy}", 0.006, 0.016, (MAST_X + dx * 0.055, MAST_Y + dy * 0.055, 0.018),
             mat=M['steel'], n=12))
reg(tube("Brazo", 0.017, abs(CAM_X - MAST_X) + 0.03, ((MAST_X + CAM_X) / 2, MAST_Y, ARM_Z),
         rot=(0, rad(90), 0), mat=M['alu'], n=32))
reg(tube("Codo", 0.026, 0.052, (MAST_X, MAST_Y, ARM_Z), mat=M['abs_mid'], n=28))

# ------------------------------------------------- camara cenital + soporte
reg(box("Camara_Soporte", (0.030, abs(CAM_Y - MAST_Y) + 0.03, 0.028),
        (CAM_X, (MAST_Y + CAM_Y) / 2, ARM_Z - 0.028), mat=M['abs_mid'], bev=0.002))
reg(box("Camara_Carcasa", (0.082, 0.072, 0.052), (CAM_X, CAM_Y, CAM_Z + 0.034), mat=M['abs'], bev=0.003, seg=3))
reg(tube("Camara_Barril", 0.016, 0.022, (CAM_X, CAM_Y, CAM_Z - 0.001), mat=M['abs'], n=32))
reg(tube("Camara_Lente", 0.0135, 0.004, (CAM_X, CAM_Y, CAM_Z - 0.012), mat=M['lens'], n=32))
for sx in (-1, 1):
    reg(tube(f"LED_IR_{sx}", 0.0055, 0.003, (CAM_X + sx * 0.028, CAM_Y, CAM_Z - 0.004), mat=M['ir'], n=16))

# visera: sombra permanente sobre el objetivo, evita sol directo y sombras moviles
# que ensucian la deteccion (DESIGN.md, notas de encuadre)
VIS_Z = ARM_Z + 0.030
reg(box("Camara_Visera", (0.205, 0.175, 0.006), (CAM_X, CAM_Y - 0.018, VIS_Z),
        rot=(rad(-9), 0, 0), mat=M['abs_mid'], bev=0.002))
for sx in (-1, 1):
    reg(box(f"Visera_Montante_{sx}", (0.010, 0.010, 0.032), (CAM_X + sx * 0.052, MAST_Y, ARM_Z + 0.015),
            mat=M['abs_mid'], bev=0.001))

# ---------------------------------------- visualizacion del plano cenital
VIZ_Z = PLANE_Z + 0.006
apex = (CAM_X, CAM_Y, CAM_Z - 0.016)
me = bpy.data.meshes.new("Frustum")
corners = [(CAM_X - HWX, CAM_Y - HWY, VIZ_Z), (CAM_X + HWX, CAM_Y - HWY, VIZ_Z),
           (CAM_X + HWX, CAM_Y + HWY, VIZ_Z), (CAM_X - HWX, CAM_Y + HWY, VIZ_Z)]
me.from_pydata([apex] + corners, [], [(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1)])
me.update()
fr = link(bpy.data.objects.new("Frustum_Camara", me))
fr.data.materials.append(M['viz'])
reg(fr)
mp = bpy.data.meshes.new("PlanoCenital")
mp.from_pydata(corners, [], [(0, 1, 2, 3)])
mp.update()
pc = link(bpy.data.objects.new("Plano_Cenital", mp))
pc.data.materials.append(M['viz'])
reg(pc)
for i, (a, b) in enumerate(zip(corners, corners[1:] + corners[:1])):
    mid = tuple((p + q) / 2 for p, q in zip(a, b))
    horiz = abs(a[0] - b[0]) > abs(a[1] - b[1])
    sz = (abs(a[0] - b[0]) + 0.004, 0.0032, 0.0011) if horiz else (0.0032, abs(a[1] - b[1]) + 0.004, 0.0011)
    reg(box(f"Borde_Cenital_{i}", sz, mid, mat=M['viz_edge'], bev=0))

print("bh_build: nucleo listo, objetos =", len(OBJ))
