# Clips

Recortes cortos y recomprimidos. Los vídeos completos no están en el repo: los
originales pesan 128-205 MB cada uno, por encima del límite de 100 MB por
fichero de GitHub, y los anotados 60-74 MB.

| Fichero | Qué es |
|---|---|
| `entrada_cenital_muestra.mp4` | 15 s de `20230711b-fan.mp4`, la entrada cruda del pipeline |
| `20230609b-def_conteo.mp4` | 20 s de la colmena tranquila, anotada |
| `20230711a-fan_conteo.mp4` | 20 s de la colmena densa: 25 abejas de media en la tabla |
| `20230711b-fan_conteo.mp4` | 20 s de la colmena con más entradas |

Los anotados se regeneran a resolución completa desde las detecciones guardadas
en `out/*_dets.npz`, sin volver a ejecutar el detector:

```bash
VIDEOS_DIR=/ruta/a/los/videos ./rerender.sh
```

Material derivado del dataset de Mendeley, CC BY 4.0. Ver [../CREDITS.md](../CREDITS.md).
