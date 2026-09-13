"""Beehaviour box - local hive monitor.

Receives sensor samples from the microcontroller over the Bridge, pushes them
straight to any connected browser for the live view, and stores a one-minute
average in the time-series database for the history. Nothing leaves the box:
the beekeeper joins the box's own WiFi and reads it from a phone.

Four sources feed the app, and two of them are stand-ins for hardware we do
not have yet. Every source declares `simulated`, and the UI labels those on
screen, so nobody demos a fabricated number believing it is a measurement:

  thermo      REAL       Modulino Thermo in the brood nest
  movement    REAL       Modulino Movement bolted to the hive
  thermo_out  SIMULATED  the second Thermo needs the other I2C bus (no cable)
  camera      SIMULATED  a recorded clip plus the per-second counts it produced

A sensor has three states, and they are not the same thing:

  absent   never seen since boot         -> the UI does not draw it at all
  present  reporting normally            -> the UI draws it
  stale    reported before, now silent   -> greyed out, with the time it stopped

The third one matters. Out in the field a sensor that goes quiet is itself
worth knowing about (loose cable, water, a chewed wire); folding it into
"absent" would show a happy screen with half the hive unmonitored.
"""

import csv
import datetime
import math
import os
import sqlite3
import threading
import time

from fastapi.responses import RedirectResponse

from arduino.app_bricks.dbstorage_tsstore import TimeSeriesStore
from arduino.app_bricks.web_ui import WebUI
from arduino.app_utils import App, Bridge

# --- config -----------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
MEDIA = os.path.join(APP, "assets", "media")
DB_PATH = os.path.join(APP, "data", "events.db")

HIVE_NAME = "Colmena 01"

# The hive is visited every one or two weeks, so a week of history (the
# brick's default) is not enough to cover "what happened since I was last here".
RETENTION_DAYS = 90

# One stored point per metric per window. The sketch samples every 2 s; keeping
# all of it would be 30x the rows for a line that would look the same.
AGGREGATE_S = 60

# A sensor that has said nothing for this long is reported as stale rather than
# present. Comfortably above the sketch's 2 s sampling and 5 s re-probe.
STALE_AFTER_S = 30

# The board has no RTC and no internet, so after a power cut the clock can come
# back in 1970 and every timestamp would be a lie.
CLOCK_SANE_AFTER = 1767225600  # 2026-01-01

SENSORS = {
    "thermo": {
        "label": "Cría",
        "metrics": ["temperature", "humidity"],
        "simulated": False,
    },
    "thermo_out": {
        "label": "Exterior",
        "metrics": ["temperature_out", "humidity_out"],
        "simulated": True,
    },
    "movement": {
        "label": "Movimiento",
        "metrics": ["accel_x", "accel_y", "accel_z"],
        "simulated": False,
    },
    "camera": {
        "label": "Piquera",
        "metrics": ["bees_on_board", "bees_in", "bees_out"],
        "simulated": True,
    },
}

# Metrics that pair up on one chart: the gap between the two lines is the
# diagnosis. A healthy colony holds the brood at 34-35 C whatever the weather
# does; when the interior line starts tracking the exterior one, they converge.
PAIRS = {
    "temperature": "temperature_out",
    "humidity": "humidity_out",
}

# --- movement alert ---------------------------------------------------------

# How far the acceleration vector has to leave its resting value to count as a
# knock, in g. A hive sitting still reads a steady 1 g downwards; a shove shows
# up immediately. Low enough to catch a firm push, high enough to ignore wind.
SHAKE_G = 0.22

# One shove must not produce forty alerts.
ALERT_COOLDOWN_S = 45

# The resting vector is learnt slowly so the alert survives the box being
# re-mounted at a slightly different angle.
BASELINE_ALPHA = 0.02


# --- state ------------------------------------------------------------------

_lock = threading.Lock()
_state = {name: {"declared": False, "last_seen": None} for name in SENSORS}
_pending = {}          # metric -> [window_start_ms, sum, count]
_latest = {}           # metric -> {"value", "ts"} - what the UI shows right now

_baseline = None       # learnt resting acceleration vector
_last_alert_ts = 0.0

_replay = []           # rows of the recorded clip: (t_s, on_board, in, out)


def now_ms():
    return int(datetime.datetime.now().timestamp() * 1000)


def clock_is_sane():
    return datetime.datetime.now().timestamp() >= CLOCK_SANE_AFTER


# --- events -----------------------------------------------------------------

def db_connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            ts       INTEGER NOT NULL,
            kind     TEXT    NOT NULL,
            severity TEXT    NOT NULL,
            title    TEXT    NOT NULL,
            detail   TEXT    NOT NULL,
            photo    TEXT,
            seen     INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    return conn


events_db = db_connect()


def add_event(kind, severity, title, detail, photo=None):
    with _lock:
        cur = events_db.execute(
            "INSERT INTO events (ts, kind, severity, title, detail, photo)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (now_ms(), kind, severity, title, detail, photo),
        )
        events_db.commit()
        event_id = cur.lastrowid
    print("aviso: %s - %s" % (title, detail))
    ui.send_message("event", read_event(event_id))


def read_event(event_id):
    row = events_db.execute(
        "SELECT id, ts, kind, severity, title, detail, photo, seen"
        " FROM events WHERE id = ?", (event_id,)).fetchone()
    return row_to_event(row) if row else None


def row_to_event(row):
    return {
        "id": row[0], "ts": row[1], "kind": row[2], "severity": row[3],
        "title": row[4], "detail": row[5], "photo": row[6], "seen": bool(row[7]),
    }


# --- the recorded clip ------------------------------------------------------

def load_replay():
    """Per-second counts produced by src/beecount.py from the very clip the
    camera view plays, so the numbers on screen and the boxes in the video are
    counting the same bees."""
    path = os.path.join(MEDIA, "piquera.csv")
    rows = []
    try:
        with open(path) as f:
            for r in csv.DictReader(f):
                rows.append((
                    float(r["t_s"]),
                    float(r["bees_on_board"]),
                    int(r["in_total"]),
                    int(r["out_total"]),
                ))
    except (OSError, KeyError, ValueError) as err:
        print("no se pudo leer el conteo grabado: %s" % err)
    return rows


def replay_cursor():
    """Where in the clip we are. The clip loops, so the camera never runs out."""
    if not _replay:
        return None
    period = _replay[-1][0]
    t = time.time() % period
    idx = min(int(t), len(_replay) - 1)
    return idx


def current_frame():
    """Which pre-extracted still matches the moment the clip is at."""
    idx = replay_cursor()
    if idx is None:
        return None
    return "media/frames/%02d.jpg" % min(idx // 10, 11)


# --- simulated outside sensor ----------------------------------------------

def outside_now():
    """A plausible March day: coldest around 06:00, warmest around 16:00, with
    humidity running opposite the temperature. Stand-in for the second Modulino
    Thermo, which cannot share the Qwiic bus with the first one."""
    now = datetime.datetime.now()
    hours = now.hour + now.minute / 60.0
    phase = math.sin((hours - 10.0) / 24.0 * 2 * math.pi)
    temp = 15.5 + 6.5 * phase
    hum = 65.0 - 20.0 * phase
    return round(temp, 1), round(hum, 1)


# --- storage ----------------------------------------------------------------

db = TimeSeriesStore(retention_days=RETENTION_DAYS)


def record(metric, value, ts):
    """Push the sample live, and store the window average when it closes."""
    _latest[metric] = {"value": value, "ts": ts}
    ui.send_message(metric, {"value": value, "ts": ts})

    window_start = ts - (ts % (AGGREGATE_S * 1000))
    acc = _pending.get(metric)

    if acc is None or acc[0] != window_start:
        if acc is not None:
            # The window just closed: store its mean, stamped at its start so
            # points land on tidy minute boundaries.
            try:
                db.write_sample(metric, acc[1] / acc[2], acc[0])
            except Exception as err:
                print("no se pudo guardar %s: %s" % (metric, err))
        _pending[metric] = [window_start, value, 1]
    else:
        acc[1] += value
        acc[2] += 1


def mark_seen(name, ts):
    with _lock:
        _state[name]["last_seen"] = ts
        _state[name]["declared"] = True


def sensor_status(name):
    with _lock:
        st = dict(_state[name])

    if st["last_seen"] is None:
        state = "present" if st["declared"] else "absent"
        return {"state": state, "last_seen": None}

    age = (now_ms() - st["last_seen"]) / 1000.0
    return {
        "state": "present" if age <= STALE_AFTER_S else "stale",
        "last_seen": st["last_seen"],
    }


# --- the simulated sources tick on their own --------------------------------

def simulation_loop():
    """The outside sensor and the camera have no microcontroller pushing them,
    so they sample themselves on the same cadence as the real ones."""
    prev_in = prev_out = None

    while True:
        ts = now_ms()

        temp, hum = outside_now()
        mark_seen("thermo_out", ts)
        record("temperature_out", temp, ts)
        record("humidity_out", hum, ts)

        idx = replay_cursor()
        if idx is not None:
            _, on_board, n_in, n_out = _replay[idx]
            mark_seen("camera", ts)
            record("bees_on_board", on_board, ts)
            # Cumulative counters restart when the clip loops; only forward
            # movement is a real arrival.
            if prev_in is not None and n_in >= prev_in:
                record("bees_in", float(n_in - prev_in), ts)
            if prev_out is not None and n_out >= prev_out:
                record("bees_out", float(n_out - prev_out), ts)
            prev_in, prev_out = n_in, n_out

        time.sleep(2)


# --- web --------------------------------------------------------------------

ui = WebUI(port=80)

# Where a phone gets sent when its OS finds the captive portal. Absolute rather
# than relative: the probe arrives with someone else's Host header (gstatic,
# apple...) and a relative redirect would leave that name in the address bar.
PORTAL_URL = "http://192.168.4.1/"

# The URLs phone operating systems fetch right after joining a WiFi to decide
# whether it reaches the internet. Answering something other than what they
# expect is what makes them pop the portal window open. No wildcard route here
# on purpose: a catch-all would shadow the static files the UI is made of.
PROBE_PATHS = [
    "/generate_204", "/gen_204",                              # Android
    "/hotspot-detect.html", "/library/test/success.html",     # iOS, macOS
    "/connecttest.txt", "/ncsi.txt", "/redirect",             # Windows
    "/canonical.html", "/success.txt",                        # Firefox
]


def on_captive_probe():
    return RedirectResponse(PORTAL_URL, status_code=302)


def on_status():
    sensors = {}
    for name, spec in SENSORS.items():
        info = sensor_status(name)
        info["label"] = spec["label"]
        info["metrics"] = spec["metrics"]
        info["simulated"] = spec["simulated"]
        sensors[name] = info

    pending = events_db.execute(
        "SELECT COUNT(*) FROM events WHERE seen = 0").fetchone()[0]

    return {
        "hive": HIVE_NAME,
        "sensors": sensors,
        "latest": _latest,
        "pairs": PAIRS,
        "pending": pending,
        "clock_ok": clock_is_sane(),
    }


def on_history(metric: str, start: str, aggr_window: str):
    try:
        samples = db.read_samples(
            measure=metric, start_from=start, aggr_window=aggr_window,
            aggr_func="mean", limit=500,
        )
    except Exception as err:
        print("no se pudo leer %s: %s" % (metric, err))
        return []
    return [{"ts": s[1], "value": s[2]} for s in samples]


def on_events():
    rows = events_db.execute(
        "SELECT id, ts, kind, severity, title, detail, photo, seen"
        " FROM events ORDER BY ts DESC LIMIT 100").fetchall()
    return [row_to_event(r) for r in rows]


def on_seen(event_id: int):
    events_db.execute("UPDATE events SET seen = 1 WHERE id = ?", (event_id,))
    events_db.commit()
    return {"ok": True}


ui.expose_api("GET", "/api/status", on_status)
ui.expose_api("GET", "/api/history/{metric}/{start}/{aggr_window}", on_history)
ui.expose_api("GET", "/api/events", on_events)
ui.expose_api("POST", "/api/events/{event_id}/seen", on_seen)

for path in PROBE_PATHS:
    ui.expose_api("GET", path, on_captive_probe)


# --- bridge callbacks -------------------------------------------------------

def sensors_detected(have_thermo: bool, have_movement: bool):
    with _lock:
        _state["thermo"]["declared"] = bool(have_thermo)
        _state["movement"]["declared"] = bool(have_movement)
    print("sensores detectados: thermo=%s movement=%s" % (have_thermo, have_movement))
    ui.send_message("sensors", on_status())


def thermo_reading(celsius: float, humidity: float):
    if celsius is None or humidity is None:
        return
    ts = now_ms()
    mark_seen("thermo", ts)
    record("temperature", float(celsius), ts)
    record("humidity", float(humidity), ts)


def movement_reading(x: float, y: float, z: float):
    global _baseline, _last_alert_ts

    if x is None or y is None or z is None:
        return

    ts = now_ms()
    mark_seen("movement", ts)
    vec = (float(x), float(y), float(z))
    record("accel_x", vec[0], ts)
    record("accel_y", vec[1], ts)
    record("accel_z", vec[2], ts)

    if _baseline is None:
        _baseline = vec
        return

    shift = math.sqrt(sum((vec[i] - _baseline[i]) ** 2 for i in range(3)))

    if shift > SHAKE_G:
        if time.time() - _last_alert_ts > ALERT_COOLDOWN_S:
            _last_alert_ts = time.time()
            tilt = math.degrees(math.atan2(
                math.sqrt(vec[0] ** 2 + vec[1] ** 2), abs(vec[2]) or 1e-6))
            add_event(
                kind="movement",
                severity="alert",
                title="GOLPE EN LA COLMENA",
                detail="Sacudida de %.2f g, inclinación de %.0f°." % (shift, tilt),
                photo=current_frame(),
            )
        # Do not learn the new position while it is being shaken.
        return

    # Quiet: drift the resting vector towards where the hive actually sits now.
    _baseline = tuple(
        _baseline[i] + BASELINE_ALPHA * (vec[i] - _baseline[i]) for i in range(3)
    )


Bridge.provide("sensors_detected", sensors_detected)
Bridge.provide("thermo_reading", thermo_reading)
Bridge.provide("movement_reading", movement_reading)

_replay = load_replay()
print("conteo grabado: %d segundos" % len(_replay))

threading.Thread(target=simulation_loop, daemon=True).start()

print("Beehaviour box arrancando...")
App.run()
