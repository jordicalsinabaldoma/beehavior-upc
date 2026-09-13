import os, traceback

# Carpeta de este fichero. Blender define __file__ al pasar --python, pero no
# al pegar el script en el editor de texto interno; de ahi el respaldo.
try:
    BASE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    BASE = os.path.join(os.getcwd(), "blender")
# Se ejecuta todo sobre el propio espacio de nombres del llamante, para que los modulos
# compartan helpers (box, viz, M, ...) y bh_shots.py pueda usarlos despues.
_G = globals()
for f in ("bh_lib.py", "bh_build.py", "bh_electronics.py", "bh_env.py",
          "bh_bees.py", "bh_render.py", "bh_post.py"):
    _p = os.path.join(BASE, f)
    try:
        exec(compile(open(_p).read(), _p, 'exec'), _G)
    except Exception:
        print("FALLO en", f)
        print(traceback.format_exc())
        break
else:
    print("=== CONSTRUCCION COMPLETA ===")
