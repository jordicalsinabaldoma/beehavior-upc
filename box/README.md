# Beehaviour box — app de la caja (Arduino UNO Q)

App de App Lab que lee los sensores de la colmena y los sirve en local, sin
internet y sin nube. Para el diseño no técnico ver [../DISEÑO.md](../DISEÑO.md).

Acabará en su propio repositorio; por ahora vive aquí.

## Estructura

```
app.yaml            declara los bricks: dbstorage_tsstore (InfluxDB) y web_ui
sketch/sketch.ino   corre en el STM32: lee los Modulino y los manda por el Bridge
sketch/sketch.yaml  versiones de librerías fijadas a lo que hay cacheado en la placa
python/main.py      corre en el Linux: agrega, guarda, sirve API y empuja el directo
assets/             la web (HTML/CSS/JS a pelo, sin framework y sin CDN)
```

## Por qué hay un sketch

El conector Qwiic de la UNO Q está cableado al **segundo bus I2C del
microcontrolador**, no al SoC Qualcomm. Desde el Linux los Modulino no se ven:
`/dev/i2c-0` está vacío, `i2c-1` es el bus interno y `i2c-2` es el canal AUX del
chip de vídeo. Así que se leen en el micro y cada muestra viaja al Python por el
Bridge (`arduino-router`, socket en `/var/run/arduino-router.sock`).

## Flujo

```
Modulino --I2C(Wire1)--> sketch --Bridge.notify--> main.py --+--> InfluxDB (histórico)
                                                             |
                                                             +--> Socket.IO (directo)
                                                             |
                                                             +--> /api/... (la web)
```

## API

| Endpoint | Qué devuelve |
|---|---|
| `GET /api/status` | qué sensores hay, su estado, últimos valores, si el reloj es fiable |
| `GET /api/history/{metric}/{start}/{window}` | serie agregada, p. ej. `/api/history/temperature/-24h/15m` |

El directo va por Socket.IO: un mensaje por métrica (`temperature`, `humidity`,
`accel_*`) y uno `sensors` cuando cambia el hardware conectado.

## Estados de sensor

No son dos, son tres, y la diferencia importa:

| Estado | Significado | La web |
|---|---|---|
| `absent` | no se ha visto desde el arranque | no lo dibuja |
| `present` | reportando | tarjeta normal |
| `stale` | reportó antes y lleva >30 s callado | tarjeta en gris con la hora del último dato |

En el campo un sensor que se calla es en sí mismo un aviso (cable suelto,
humedad, un bicho). Meterlo en `absent` enseñaría una pantalla feliz con media
colmena sin vigilar.

## Conectarse desde el móvil

La caja levanta su propia red. No hay internet detrás: la contraseña del WiFi es
toda la autenticación, la API no lleva login.

| | |
|---|---|
| Red | `beehaviour-colmena-01` |
| Contraseña | `colmena2026` |
| Dirección | http://192.168.4.1 (o `Beehaviour.local`) |

El AP es una conexión de NetworkManager llamada `beehaviour-ap`: WPA2-CCMP,
banda 2,4 GHz canal 6, `ipv4.method shared` con IP fija 192.168.4.1/24. El DHCP
lo pone el dnsmasq que NetworkManager arranca para el modo compartido, con rango
.10–.254.

Está en `autoconnect yes` con `autoconnect-priority -999`, o sea que si hay una
red conocida al alcance la placa se conecta a ella, y si no levanta la suya. Así
se puede seguir entrando por SSH en casa sin perder el comportamiento de campo.

```bash
nmcli connection up beehaviour-ap     # levantarlo a mano
nmcli connection down beehaviour-ap   # bajarlo
```

### Portal cautivo

La app escucha en el **puerto 80** y responde a las URLs que los móviles piden
nada más conectarse para comprobar si hay internet (`/generate_204` en Android,
`/hotspot-detect.html` en iOS, etc.) con un 302 a `http://192.168.4.1/`. El
sistema operativo lo interpreta como "aquí hay un portal" y abre la pantalla
solo.

Son rutas concretas, no un comodín: una ruta `/{path:path}` taparía los ficheros
estáticos de los que está hecha la propia web.

Para que funcione falta además que el DNS resuelva *cualquier* dominio a la caja.
Eso toca un fichero de root, así que hay que ponerlo a mano una vez:

```bash
adb shell -t 'sudo sh -c "echo address=/#/192.168.4.1 > /etc/NetworkManager/dnsmasq-shared.d/beehaviour-captive.conf"'
adb shell 'nmcli connection down beehaviour-ap; nmcli connection up beehaviour-ap'
```

Sin eso la web sigue funcionando escribiendo la dirección, pero la pantalla no
salta sola.

## Ejecutar

Con la placa conectada por USB:

```bash
adb push box/. /home/arduino/ArduinoApps/beehaviour-box/
adb shell 'TMPDIR=/tmp arduino-app-cli app start user:beehaviour-box'
adb shell 'TMPDIR=/tmp arduino-app-cli app logs user:beehaviour-box'
```

Para verlo desde el portátil sin WiFi todavía, se redirige el puerto por el
propio cable:

```bash
adb forward tcp:7000 tcp:7000
# y abrir http://localhost:7000
```

## Trampas encontradas

- **`TMPDIR`**. El demonio de ADB fija `TMPDIR=/data/local/tmp`, que es una ruta
  de Android y en el Debian de la placa no existe. Sin `TMPDIR=/tmp` delante, la
  grabación del sketch falla con `Stat /Data/Local/Tmp: No Such File Or
  Directory`. Solo pasa por ADB; desde App Lab o por SSH no.
- **Librerías sin red**. La placa no tiene internet, así que el `sketch.yaml`
  tiene que pedir exactamente las versiones cacheadas en
  `/home/arduino/.arduino15/internal`. Cualquier otra manda la compilación a
  `downloads.arduino.cc` y falla. Ojo: ahí está `ArxTypeTraits 0.3.2` y
  `Arduino_Modulino 0.6.1`, no las del ejemplo oficial.
- **Sin CDN**. Los ejemplos de Arduino cargan Chart.js desde jsdelivr. Aquí las
  gráficas son SVG dibujado a mano para no depender de internet.
- **Retención**. `TimeSeriesStore` guarda 7 días por defecto. La colmena se
  visita cada una o dos semanas, así que está puesto a 90.
- **El reloj**. La placa no tiene RTC ni NTP: al conectarla iba seis semanas
  atrasada. `/api/status` devuelve `clock_ok` comparando con 2026-01-01, pero eso
  solo detecta el caso salvaje. Pendiente de que la app corrija el desfase con la
  hora del móvil.

## Un solo Thermo

El Modulino Thermo es un HS3003 con dirección I2C fija (`0x44`) y sin pin de
selección, así que **dos no pueden compartir el Qwiic**. El segundo tendría que
colgar del otro bus (`Wire`, pines SDA/SCL del header, PB11/PB10) instanciando
`HS300xClass(Wire)` y saltándose el envoltorio Modulino. Hace falta un cable
Qwiic con los hilos sueltos. Mientras tanto la app funciona con uno.

## Pendiente

- El DNS comodín del portal cautivo (ver arriba, necesita root una vez).
- Corrección de reloj con la hora del móvil.
- Sensor exterior, cuando haya cable.
- Cámara: el conteo de abejas de `../src/` escribiendo en la misma base.
