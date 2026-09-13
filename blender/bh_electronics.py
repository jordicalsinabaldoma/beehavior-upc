# -*- coding: utf-8 -*-
"""Caja de control, sensores y bus de cableado en serie."""
import bpy, math
from math import radians as rad

# ------------------------------------------------------- caja estanca IP65
EX, EY, EZ = -0.50, -0.357, 0.66
# carcasa hueca: 5 caras, abierta hacia -Y para que la tapa deje ver la placa
CW = 0.006                                   # espesor de pared
reg(box("Caja_Fondo", (0.175, CW, 0.125), (EX, EY + 0.036 - CW / 2, EZ), mat=M['abs'], bev=0.002))
for dz in (-1, 1):
    reg(box(f"Caja_Pared_Z_{dz}", (0.175, 0.072, CW), (EX, EY, EZ + dz * (0.0625 - CW / 2)),
            mat=M['abs'], bev=0.002))
for dx in (-1, 1):
    reg(box(f"Caja_Pared_X_{dx}", (CW, 0.072, 0.125 - 2 * CW), (EX + dx * (0.0875 - CW / 2), EY, EZ),
            mat=M['abs'], bev=0.002))
for dz in (-1, 1):   # marco frontal donde apoya la tapa
    reg(box(f"Caja_Reborde_Z_{dz}", (0.181, 0.008, 0.011), (EX, EY - 0.032, EZ + dz * 0.060),
            mat=M['abs'], bev=0.0015))
for dx in (-1, 1):
    reg(box(f"Caja_Reborde_X_{dx}", (0.011, 0.008, 0.131), (EX + dx * 0.085, EY - 0.032, EZ),
            mat=M['abs'], bev=0.0015))
reg(box("Caja_Tapa", (0.181, 0.014, 0.131), (EX, EY - 0.043, EZ), mat=M['poly'], bev=0.003, seg=3))
for dx, dz in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
    reg(tube(f"Caja_Tornillo_{dx}_{dz}", 0.0045, 0.006,
             (EX + dx * 0.079, EY - 0.051, EZ + dz * 0.054), rot=(rad(90), 0, 0), mat=M['steel'], n=6))
for dz in (-1, 1):
    reg(box(f"Caja_Soporte_{dz}", (0.030, 0.020, 0.032), (EX, EY + 0.040, EZ + dz * 0.042),
            mat=M['abs_mid'], bev=0.002))
for gx, gz, gh in ((-0.055, 0.0735, 1), (0.020, 0.0735, 1), (-0.055, -0.0735, -1)):
    reg(tube(f"Prensaestopa_{gx}_{gz}", 0.009, 0.024, (EX + gx, EY, EZ + gz + gh * 0.010),
             mat=M['abs_mid'], n=16))
reg(tube("Antena_Base", 0.008, 0.014, (EX + 0.070, EY + 0.010, EZ + 0.069), mat=M['abs_mid'], n=14))
reg(tube("Antena", 0.0045, 0.098, (EX + 0.083, EY + 0.010, EZ + 0.118), rot=(0, rad(22), 0),
         mat=M['abs'], n=14))

# placa de montaje: en una caja real el PCB va sobre un panel claro, que ademas
# rebota luz hacia los componentes y evita que el interior salga negro
reg(box("Caja_Placa_Montaje", (0.160, 0.003, 0.110), (EX, EY + 0.026, EZ),
        mat=pbr("Panel Montaje", (0.512, 0.528, 0.540), 0.0, 0.52), bev=0.001))

# -------------------------------------------------------------------- PCB
PX, PY, PZ = EX, EY - 0.016, EZ
reg(box("PCB", (0.150, 0.0016, 0.098), (PX, PY, PZ), mat=M['pcb'], bev=0.0008))
for dx, dz in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
    reg(tube(f"PCB_Separador_{dx}_{dz}", 0.0035, 0.014, (PX + dx * 0.068, PY + 0.008, PZ + dz * 0.042),
             rot=(rad(90), 0, 0), mat=M['steel'], n=10))

# SoC Qualcomm con disipador integrado
reg(box("SoC_Qualcomm", (0.028, 0.0042, 0.028), (PX + 0.030, PY - 0.003, PZ + 0.016), mat=M['chip'], bev=0.0006))
reg(box("SoC_Disipador", (0.022, 0.0011, 0.022), (PX + 0.030, PY - 0.0056, PZ + 0.016), mat=M['steel'], bev=0.0004))
# microcontrolador Arduino
reg(box("MCU_Arduino", (0.015, 0.0030, 0.015), (PX - 0.038, PY - 0.0023, PZ + 0.018), mat=M['chip'], bev=0.0005))
# blindaje RF
reg(box("Blindaje_RF", (0.026, 0.0030, 0.019), (PX + 0.030, PY - 0.0023, PZ - 0.022), mat=M['steel'], bev=0.0005))
# regleta de sensores (aqui aterriza el bus en serie)
reg(box("Regleta_Sensores", (0.058, 0.015, 0.017), (PX - 0.044, PY - 0.0075, PZ - 0.032), mat=M['pcb'], bev=0.0008))
for i in range(6):
    reg(tube(f"Regleta_Tornillo_{i}", 0.0022, 0.003, (PX - 0.044 + (i - 2.5) * 0.0092, PY - 0.0152, PZ - 0.032),
             rot=(rad(90), 0, 0), mat=M['steel'], n=8))
# tira de pines
reg(box("Tira_Pines", (0.060, 0.0055, 0.009), (PX + 0.010, PY - 0.0035, PZ - 0.038), mat=M['chip'], bev=0.0004))
for i in range(12):
    reg(tube(f"Pin_{i}", 0.0006, 0.010, (PX + 0.010 + (i - 5.5) * 0.005, PY - 0.0075, PZ - 0.038),
             rot=(rad(90), 0, 0), mat=M['gold'], n=6))
# USB-C, condensadores y LEDs
reg(box("USB_C", (0.010, 0.0078, 0.0034), (PX + 0.066, PY - 0.0047, PZ + 0.040), mat=M['steel'], bev=0.0004))
for i, (cx, cz) in enumerate(((-0.012, 0.034), (0.002, 0.034), (-0.062, -0.006))):
    reg(tube(f"Condensador_{i}", 0.0038, 0.0085, (PX + cx, PY - 0.0051, PZ + cz), rot=(rad(90), 0, 0),
             mat=M['abs_mid'], n=14))
reg(box("LED_PWR", (0.0032, 0.0016, 0.0018), (PX - 0.070, PY - 0.0024, PZ + 0.040), mat=M['led_g'], bev=0))
reg(box("LED_ACT", (0.0032, 0.0016, 0.0018), (PX - 0.062, PY - 0.0024, PZ + 0.040), mat=M['led_b'], bev=0))

# ------------------------------------------- termometro exterior con abrigo
SH_X = MAST_X - 0.155
SH_Z = 0.790
reg(tube("Abrigo_Brazo", 0.008, abs(MAST_X - 0.021 - SH_X) + 0.02,
         ((MAST_X - 0.021 + SH_X) / 2, MAST_Y, SH_Z), rot=(0, rad(90), 0), mat=M['alu'], n=16))
reg(tube("Abrigo_Tapa", 0.047, 0.006, (SH_X, MAST_Y, SH_Z), mat=M['white'], n=36))
for i in range(5):
    reg(tube(f"Abrigo_Lama_{i}", 0.045, 0.005, (SH_X, MAST_Y, SH_Z - 0.012 - i * 0.012),
             r2=0.034, mat=M['white'], n=36))
reg(tube("Abrigo_Eje", 0.004, 0.056, (SH_X, MAST_Y, SH_Z - 0.032), mat=M['steel'], n=10))
reg(tube("Termo_Exterior", 0.0058, 0.030, (SH_X, MAST_Y, SH_Z - 0.042), mat=M['white'], n=20))
reg(tube("Termo_Exterior_Punta", 0.0042, 0.008, (SH_X, MAST_Y, SH_Z - 0.060), mat=M['steel'], n=16))

# ------------------------------------- sensor de movimiento (acelerometro)
# DISENO.md 3.3: detecta robo, vuelco o golpe, asi que va atornillado rigido a la
# estructura, no mirando a las abejas. Bajo el vuelo del techo, protegido de la lluvia.
IMU_X = -(BX + 0.011)
IMU_Y, IMU_Z = -0.060, 0.790
reg(box("Modulo_Movimiento", (0.022, 0.056, 0.044), (IMU_X, IMU_Y, IMU_Z), mat=M['abs_mid'], bev=0.003))
reg(box("Modulo_Movimiento_Etiqueta", (0.001, 0.030, 0.012), (IMU_X - 0.0115, IMU_Y, IMU_Z + 0.010),
        mat=M['white'], bev=0))
for dz in (-1, 1):
    reg(tube(f"Modulo_Movimiento_Tornillo_{dz}", 0.0035, 0.005,
             (IMU_X - 0.0115, IMU_Y, IMU_Z + dz * 0.016), rot=(0, rad(90), 0), mat=M['steel'], n=8))
reg(tube("Modulo_Movimiento_Prensa", 0.006, 0.014, (IMU_X, IMU_Y, IMU_Z - 0.026), mat=M['abs_mid'], n=14))

# ------------------------------------------------- termometro interior
reg(box("Termo_Interior_Brazo", (0.009, 0.046, 0.009), (-0.055, -0.168, 0.6775), mat=M['abs_mid'], bev=0.001))
reg(box("Termo_Interior_Montante", (0.009, 0.009, 0.030), (-0.055, -0.154, 0.6625), mat=M['abs_mid'], bev=0.001))
reg(tube("Termo_Interior", 0.0058, 0.050, (-0.055, -0.154, 0.6225), mat=M['white'], n=20))
reg(tube("Termo_Interior_Punta", 0.0042, 0.010, (-0.055, -0.154, 0.5935), mat=M['steel'], n=16))

# ---------------------------------------------- pasamuros en la pared lateral
reg(tube("Pasamuros", 0.011, 0.020, (-BX, -0.050, 0.618), rot=(0, rad(90), 0), mat=M['rubber'], n=20))

# ------------------------------------------------- bus de sensores en serie
reg(cable("Bus_1_Caja_a_TermoExt", [
    (EX - 0.055, EY, EZ + 0.084), (-0.580, -0.340, 0.760), (-0.620, -0.318, 0.775), (SH_X, -0.302, 0.772)
], 0.0026, M['rubber']))
reg(cable("Bus_2_TermoExt_a_Movimiento", [
    (SH_X, MAST_Y, SH_Z - 0.050), (SH_X + 0.030, -0.302, 0.760), (MAST_X, -0.300, 0.772),
    (-0.440, -0.240, 0.780), (-0.350, -0.150, 0.778), (-0.290, -0.090, 0.776),
    (IMU_X, IMU_Y, IMU_Z - 0.030)
], 0.0026, M['rubber']))
reg(cable("Bus_3_Movimiento_a_Colmena", [
    (IMU_X, IMU_Y, IMU_Z - 0.032), (-0.262, -0.058, 0.720), (-0.258, -0.054, 0.660),
    (-0.256, -0.052, 0.624)
], 0.0026, M['rubber']))
reg(cable("Bus_4_Interior_a_TermoInt", [
    (-0.248, -0.050, 0.618), (-0.240, -0.096, 0.642), (-0.218, -0.136, 0.660),
    (-0.168, -0.158, 0.665), (-0.100, -0.160, 0.664), (-0.058, -0.158, 0.660)
], 0.0024, M['rubber']))
reg(cable("Bus_5_Camara", [
    (EX + 0.020, EY, EZ + 0.084), (-0.486, -0.332, 0.775), (-0.497, -0.310, 0.808),
    (MAST_X, -0.300, ARM_Z + 0.005), (-0.470, -0.290, ARM_Z + 0.019),
    (-0.300, -0.288, ARM_Z + 0.019), (-0.120, -0.292, ARM_Z + 0.017),
    (-0.040, -0.305, ARM_Z - 0.010), (CAM_X, CAM_Y, CAM_Z + 0.052)
], 0.0028, M['rubber']))
for x in (-0.40, -0.25, -0.10):
    reg(tube(f"Brida_Brazo_{x}", 0.0205, 0.005, (x, MAST_Y, ARM_Z), rot=(0, rad(90), 0),
             mat=M['rubber'], n=24, caps=False))
for dz in (0.10, 0.20):
    reg(tube(f"Brida_Mastil_{dz}", 0.0245, 0.006, (MAST_X, MAST_Y, ARM_Z - dz),
             mat=M['rubber'], n=24, caps=False))

# ------------------------------------------------------------------ terreno
g = box("Terreno", (26, 26, 0.02), (0, 0, -0.01), mat=M['ground'], bev=0)
reg(g)
nt = M['ground'].node_tree
b = _bsdf(M['ground'])
co = nt.nodes.new('ShaderNodeTexCoord'); nz = nt.nodes.new('ShaderNodeTexNoise')
ra = nt.nodes.new('ShaderNodeValToRGB'); bp = nt.nodes.new('ShaderNodeBump')
nz.inputs['Scale'].default_value = 12.0
nz.inputs['Detail'].default_value = 14.0
ra.color_ramp.elements[0].color = (0.038, 0.052, 0.018, 1)
ra.color_ramp.elements[1].color = (0.168, 0.192, 0.086, 1)
bp.inputs['Strength'].default_value = 0.55
nt.links.new(co.outputs['Object'], nz.inputs['Vector'])
nt.links.new(nz.outputs['Fac'], ra.inputs['Fac'])
nt.links.new(ra.outputs['Color'], b.inputs['Base Color'])
nt.links.new(nz.outputs['Fac'], bp.inputs['Height'])
nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])

print("bh_electronics: total objetos =", len(OBJ))
