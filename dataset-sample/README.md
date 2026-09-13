# Muestra del dataset

Un puñado de ficheros del dataset de Mendeley, para poder ver el formato y
probar los scripts sin descargar los 7,8 GB. **No sirve para entrenar**: son 14
fotogramas.

```
images/   14 fotogramas JPEG de 640x360, 2-3 por colmena, del split de validación
labels/   sus etiquetas en formato YOLO: `0 cx cy w h`, normalizado, clase 0 = bee
zones/    el polígono de la tabla de vuelo de cada uno de los 3 vídeos de prueba
```

Las colmenas presentes aquí (`20230609a`, `20230609c`, `20230609d`, `20230609e`,
`20230711c`) son las de entrenamiento y validación. Las tres de los vídeos de
prueba (`20230609b`, `20230711a`, `20230711b`) quedan fuera a propósito: son las
que se usan para evaluar, y el modelo no las ha visto nunca.

## Las zonas

`zones/entrance_zone_<vídeo>.txt` contiene un polígono de cuatro esquinas en
coordenadas de 1920x1080:

```
polygon = np.array([[245, 482], [1621, 482], [1617, 750], [255, 754]])
```

Es la tabla de vuelo. Su borde superior, el que da a la colmena, es la línea de
entrada que usa el conteo. `beecount.py --zone` lo lee y lo reescala al tamaño
del fotograma, así que la piquera no se ajusta a mano por cámara.

## Dataset completo

<https://doi.org/10.17632/8gb9r2yhfc.6> — CC BY 4.0. Ver [../CREDITS.md](../CREDITS.md)
para la cita.

Una vez descargado, `src/build_dataset.py --src "<dataset>/detection"` monta el
dataset YOLO entero repartiendo por colmena.
