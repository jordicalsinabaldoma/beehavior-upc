# Beehaviour box: the app on the board (Arduino UNO Q)

An App Lab app that reads the hive's sensors and serves them locally, with no
internet and no cloud. For the non-technical design see [../DESIGN.md](../DESIGN.md).

It will end up in its own repository; for now it lives here.

## What it looks like

| Alerts | Monitoring | Live entrance |
|---|---|---|
| ![Alert list](../docs/app/alerts.png) | ![Monitoring screen](../docs/app/monitor.png) | ![Live entrance view](../docs/app/live.png) |

## Layout

```
app.yaml            declares the bricks: dbstorage_tsstore (InfluxDB) and web_ui
sketch/sketch.ino   runs on the STM32: reads the Modulinos and sends them over the Bridge
sketch/sketch.yaml  library versions pinned to whatever is cached on the board
python/main.py      runs on the Linux side: aggregates, stores, serves the API and pushes live data
assets/             the web UI (plain HTML/CSS/JS, no framework and no CDN)
```

## Why there is a sketch at all

The UNO Q's Qwiic connector is wired to the microcontroller's second I2C bus,
not to the Qualcomm SoC. From Linux the Modulinos are invisible: `/dev/i2c-0` is
empty, `i2c-1` is the internal bus and `i2c-2` is the video chip's AUX channel.
So they are read on the MCU and each sample travels to Python over the Bridge
(`arduino-router`, socket at `/var/run/arduino-router.sock`).

## Flow

```
Modulino --I2C(Wire1)--> sketch --Bridge.notify--> main.py --+--> InfluxDB (history)
                                                             |
                                                             +--> Socket.IO (live)
                                                             |
                                                             +--> /api/... (the web UI)
```

## API

| Endpoint | What it returns |
|---|---|
| `GET /api/status` | which sensors are there, their state, latest values, whether the clock is trustworthy |
| `GET /api/history/{metric}/{start}/{window}` | an aggregated series, e.g. `/api/history/temperature/-24h/15m` |

Live data goes over Socket.IO: one message per metric (`temperature`,
`humidity`, `accel_*`) and one `sensors` message when the attached hardware
changes.

## Sensor states

There are three, not two, and the difference matters:

| State | Meaning | The web UI |
|---|---|---|
| `absent` | not seen since boot | does not draw it |
| `present` | reporting | normal card |
| `stale` | reported before, silent for >30 s | greyed-out card with the time of the last reading |

Out in the field, a sensor that goes quiet is itself an alert (a loose cable,
damp, an insect). Folding it into `absent` would show a cheerful screen with
half the hive unmonitored.

## Connecting from a phone

The box brings up its own network. There is no internet behind it: the WiFi
password is the whole of the authentication, the API has no login.

| | |
|---|---|
| Network | `beehaviour-colmena-01` |
| Password | `colmena2026` |
| Address | http://192.168.4.1 (or `Beehaviour.local`) |

The AP is a NetworkManager connection called `beehaviour-ap`: WPA2-CCMP, 2.4 GHz
band channel 6, `ipv4.method shared` with a static 192.168.4.1/24. DHCP comes
from the dnsmasq that NetworkManager starts for shared mode, range .10-.254.

It is set to `autoconnect yes` with `autoconnect-priority -999`, meaning that if
a known network is in range the board joins it, and otherwise brings up its own.
That way you can still SSH into it at home without losing the field behaviour.

```bash
nmcli connection up beehaviour-ap     # bring it up by hand
nmcli connection down beehaviour-ap   # take it down
```

### Captive portal

The app listens on port 80 and answers the URLs phones request right after
connecting, to check whether there is internet (`/generate_204` on Android,
`/hotspot-detect.html` on iOS, and so on), with a 302 to `http://192.168.4.1/`.
The operating system reads that as "there is a portal here" and opens the screen
by itself.

These are specific routes, not a catch-all: a `/{path:path}` route would shadow
the static files the web UI is made of.

For it to work, DNS also has to resolve *any* domain to the box. That touches a
root-owned file, so it has to be set up by hand once:

```bash
adb shell -t 'sudo sh -c "echo address=/#/192.168.4.1 > /etc/NetworkManager/dnsmasq-shared.d/beehaviour-captive.conf"'
adb shell 'nmcli connection down beehaviour-ap; nmcli connection up beehaviour-ap'
```

Without it the web UI still works if you type the address, but the screen does
not pop up on its own.

## Running it

With the board connected over USB:

```bash
adb push box/. /home/arduino/ArduinoApps/beehaviour-box/
adb shell 'TMPDIR=/tmp arduino-app-cli app start user:beehaviour-box'
adb shell 'TMPDIR=/tmp arduino-app-cli app logs user:beehaviour-box'
```

To see it from a laptop before the WiFi is up, forward the port over the cable
itself:

```bash
adb forward tcp:7000 tcp:7000
# then open http://localhost:7000
```

## Traps found along the way

- `TMPDIR`. The ADB daemon sets `TMPDIR=/data/local/tmp`, an Android path that
  does not exist on the board's Debian. Without `TMPDIR=/tmp` in front, flashing
  the sketch fails with `Stat /Data/Local/Tmp: No Such File Or Directory`. It only
  happens over ADB; from App Lab or over SSH it does not.
- Libraries with no network. The board has no internet, so `sketch.yaml` has to
  ask for exactly the versions cached in `/home/arduino/.arduino15/internal`.
  Anything else sends the build off to `downloads.arduino.cc` and it fails. Note
  those are `ArxTypeTraits 0.3.2` and `Arduino_Modulino 0.6.1`, not the ones from
  the official example.
- No CDN. The Arduino examples load Chart.js from jsdelivr. Here the charts are
  hand-drawn SVG, so nothing depends on the internet.
- Retention. `TimeSeriesStore` keeps 7 days by default. The hive is visited
  every one or two weeks, so it is set to 90.
- The clock. The board has no RTC and no NTP: out of the box it was six weeks
  behind. `/api/status` returns `clock_ok` by comparing against 2026-01-01, but
  that only catches the wild case. Still to do: have the app correct the offset
  from the phone's time.

## Only one Thermo

The Modulino Thermo is an HS3003 with a fixed I2C address (`0x44`) and no select
pin, so two cannot share the Qwiic bus. The second one would have to hang off
the other bus (`Wire`, the header's SDA/SCL pins, PB11/PB10), instantiating
`HS300xClass(Wire)` and bypassing the Modulino wrapper. That needs a Qwiic cable
with loose leads. In the meantime the app works with one.

## To do

- The captive portal's wildcard DNS (see above, needs root once).
- Clock correction from the phone's time.
- The outdoor sensor, once there is a cable.
- The camera: bee counting from `../src/` writing into the same database.
