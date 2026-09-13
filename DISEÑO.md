# Beehaviour — Guardián de colmena local

Proyecto de hackathon. Prueba de concepto (PoC) de una caja de vigilancia para colmenas que funciona sin internet, sin cobertura y sin nube. Todo se procesa dentro del propio dispositivo instalado en la colmena.

---

## 1. El problema

Los apicultores tienen sus colmenares en el campo, muchas veces sin cobertura móvil. Visitan las colmenas cada una o dos semanas. Entre visita y visita pueden pasar cosas graves que no se detectan a tiempo:

- La colonia enjambra y se pierde la mitad de las abejas.
- La reina muere y la colonia se apaga en pocas semanas.
- Un avispón asiático se instala en la piquera y bloquea la colmena.
- Alguien roba la colmena, o un animal o el viento la vuelca.
- Una fumigación cercana mata a cientos de abejas en una tarde.

Cuando el apicultor llega, a menudo ya es tarde.

## 2. La idea

Una pequeña caja con una cámara y dos sensores que vive en la colmena, observa la piquera las 24 horas y aprende cómo es un día normal de esa colmena. Cuando algo se sale de lo normal, lo registra con hora y foto. Cuando el apicultor llega al colmenar, se conecta con el móvil y ve de un vistazo qué ha pasado desde la última visita.

No necesita internet en ningún momento. Toda la inteligencia está dentro de la caja.

## 3. Qué vigila

### 3.1 Cámara en la piquera

La cámara va montada unos 30 cm por encima de la tabla de vuelo, mirando hacia abajo, de modo que ve la tabla y la ranura de entrada. Con esa imagen el sistema hace tres cosas:

**Actividad de la colmena.** Cuenta cuántas abejas hay en la piquera en cada momento y cuántas entran y salen. Con eso construye la curva de actividad de cada día: poca al amanecer, mucha al mediodía, nada de noche. Cada colmena tiene su propia curva.

**Aviso de actividad anormal.** Si un día a una hora de buen tiempo la actividad es mucho menor o mucho mayor de lo habitual, avisa. No dice la causa, dice "aquí pasa algo, ven a mirar". Esto cubre de golpe varios problemas distintos:

| Situación | Lo que se ve en la piquera |
|---|---|
| Enjambrazón (la colonia se divide y media se marcha) | Explosión de actividad un mediodía y después la mitad de tráfico durante días |
| Intoxicación por pesticidas | Caída brusca de actividad en pocas horas |
| Abejaruco cazando cerca | Las abejas dejan de salir en horas buenas |
| Pillaje (otras colmenas roban la miel) | Tráfico caótico y mucho mayor de lo normal |
| Colonia débil o enferma | Actividad que baja poco a poco durante semanas |

**Aviso de intruso.** El sistema sabe qué aspecto tiene una abeja. Si aparece en la piquera algo que se mueve y claramente no es una abeja, sobre todo si es bastante más grande, avisa y guarda una foto. Esto detecta el avispón asiático (Vespa velutina), el avispón europeo, avispas, un ratón, un pájaro posado o una mano tocando la colmena. No identifica la especie, pero el apicultor ve la foto y lo sabe al momento.

### 3.2 Dos sensores de temperatura y humedad

Uno dentro de la colmena, en la zona de cría. Otro fuera, a la sombra.

Una colonia sana mantiene la cría a unos 34 o 35 grados pase lo que pase fuera, en invierno y en verano. Comparar los dos sensores dice mucho:

| Situación | Lo que se ve |
|---|---|
| Colonia sana | Temperatura interior estable aunque la exterior suba y baje |
| Colonia huérfana o muy débil | La temperatura interior empieza a seguir a la exterior |
| Enjambrazón próxima | Sube la temperatura y la humedad interior los días antes |
| Riesgo de hongos y condensación en invierno | Humedad interior alta durante días con temperatura baja |

### 3.3 Sensor de movimiento

Va fijado a la caja de la colmena. Detecta si la colmena se mueve, se inclina o recibe un golpe. Sirve para:

- Robo de la colmena.
- Vuelco por viento o por un animal (jabalí, tejón).
- Golpes o manipulación fuera de horas de visita.

Cuando salta, la cámara guarda una foto del momento.

## 4. Cómo lo ve el apicultor

Al llegar al colmenar, el apicultor conecta el móvil o el portátil a la caja. Durante el desarrollo se hará por cable. Más adelante la propia caja creará una red WiFi local, sin internet, a la que el móvil se conecta como si fuera la de casa.

Se abre una pantalla sencilla con:

- Lista de avisos desde la última visita, con fecha, hora y foto si la hay.
- Gráfica de actividad de los últimos días.
- Gráfica de temperatura y humedad interior y exterior.
- Estado actual de la colmena.

## 5. Qué queda fuera de esta prueba de concepto

Se ha decidido no incluir, por ahora:

- Identificar la especie exacta del intruso. Solo se avisa de "algo que no es una abeja".
- Contar abejas muertas en la piquera.
- Distinguir el color del polen que traen las abejas.
- Inspección de cuadros con cámara al abrir la colmena.
- Asistente de texto que recomiende al apicultor qué hacer.
- Botones físicos para registrar inspecciones.
- Envío de alertas a distancia por radio (LoRa). Se contempla como paso siguiente: la caja seguiría trabajando en local y solo enviaría avisos cortos.
- Aprendizaje avanzado del patrón de la colmena. Por ahora se usan reglas sencillas de "fuera de lo habitual".

## 6. Cómo se demuestra en la hackathon

No habrá colmena real. La demostración se hace así:

- **Cámara:** el sistema procesa vídeos reales de piqueras grabados desde arriba. Se muestra el conteo de abejas y la curva de actividad en directo. Para el aviso de intruso se usa un vídeo con un avispón o se coloca un objeto oscuro sobre una tabla real delante de la cámara.
- **Temperatura:** se calienta un sensor con la mano o se enfría para provocar la alerta de colonia débil.
- **Movimiento:** se empuja o inclina la caja para provocar la alerta de robo o vuelco.
- **Pantalla:** se muestra el historial y los avisos en el móvil o portátil conectado.

---

## 7. Material

### Hardware disponible

- Arduino UNO Q (Qualcomm Dragonwing QRB2210, 4 GB RAM, 32 GB de disco). Lleva WiFi y Bluetooth integrados.
- Modulino Thermo x2 (temperatura y humedad).
- Modulino Movement (acelerómetro y giroscopio).
- Modulino Buttons (no se usa en esta PoC).
- Cámara conectable.

### Dataset

**Bee Detection and Direction Estimation Dataset**
https://data.mendeley.com/datasets/8gb9r2yhfc/6

- Universidad Técnica Gediminas de Vilnius (Lituania). Versión 6, agosto 2024. Licencia CC BY 4.0, uso libre citando la fuente.
- Cámara a 30 cm sobre la tabla de vuelo, 8 colmenas, verano 2023. Es exactamente el ángulo de cámara elegido para el proyecto.
- Contiene:
  - 7.200 imágenes a 1920x1080 con las abejas marcadas.
  - Vídeos con unas 17.000 trayectorias de abejas ya anotadas, unos 7 minutos en total.
  - 400 imágenes con la posición de cabeza y aguijón de cada abeja (orientación).
  - 156 imágenes con las esquinas de la tabla de vuelo marcadas.
  - Etiquetas de comportamiento: pecoreo, defensa, ventilación, "washboarding".
- Solo hay abejas. No hay avispas ni avispones. Por eso la detección de intruso se plantea como "algo que no es una abeja" y no como identificación de especie.

### Vídeos de referencia

- Bee happy, detección, seguimiento y conteo de abejas desde arriba. Referencia del resultado que se busca y del encuadre de cámara.
  https://www.youtube.com/watch?v=e2AaZVANBX8
- Vídeo de piquera para demo y pruebas.
  https://www.youtube.com/watch?v=bg7paGfvTHI
- Canal BeeHiveCastle, cámara de piquera en directo 24/7, plano en tres cuartos desde arriba. Fuente de clips largos con mucha actividad.
  https://www.youtube.com/@BeeHiveCastle

### Notas sobre el encuadre de cámara

- Elegido: casi cenital, unos 30 cm sobre la tabla de vuelo, como en el dataset de Mendeley.
- Dejar margen de tabla y de aire delante de la entrada, porque el avispón se queda quieto en el aire o posado justo ahí.
- Tabla de vuelo de color claro y mate facilita mucho la detección.
- Visera sobre la cámara para evitar sol directo y sombras móviles.
- Descartados: plano frontal a la ranura (las abejas se tapan unas a otras) y plano general de la colmena (las abejas se ven demasiado pequeñas).

### Glosario rápido

- **Piquera:** ranura de entrada de la colmena.
- **Tabla de vuelo:** repisa delante de la piquera donde aterrizan las abejas.
- **Enjambrazón:** la colonia se divide y la mitad se marcha con la reina vieja. Pérdida de abejas y de cosecha.
- **Colonia huérfana:** colonia sin reina. Sin cría nueva, se extingue en semanas.
- **Vespa velutina:** avispón asiático, especie invasora que caza abejas en la piquera. Presente en Cataluña y el norte de España.
- **Abejaruco:** pájaro migratorio que come abejas al vuelo. Caza a distancia, no se posa en la piquera.
- **Varroa:** ácaro parásito de la abeja, principal causa de pérdida de colmenas en el mundo. No se detecta directamente en esta PoC.
- **Pillaje:** abejas de otras colmenas que entran a robar miel de una colmena débil.
