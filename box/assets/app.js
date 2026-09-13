// Beehaviour box - front end.
//
// Two halves, because they answer different questions at different moments:
// AVISOS is "what happened while I was away" - read once, on arrival, in the
// past tense. MONITOREO is "what is happening and how has it been trending" -
// browsed, with charts and a time range. Everything on screen is driven by
// /api/status: the box says which sensors it can see and which of them are
// stand-ins, and this file draws those and only those.

const socket = io(`http://${window.location.host}`);
const api = (path) => `http://${window.location.host}${path}`;

// How each metric is shown. A metric the box reports but that is not listed
// here still appears, just without a unit or a nice name.
const METRICS = {
  temperature:     { label: "Temperatura de la cría", short: "CRÍA",       unit: "°C", dec: 1, band: [34, 35] },
  temperature_out: { label: "Temperatura exterior",   short: "EXTERIOR",   unit: "°C", dec: 1 },
  humidity:        { label: "Humedad interior",       short: "HUMEDAD",    unit: "%",  dec: 0 },
  humidity_out:    { label: "Humedad exterior",       short: "H. EXT",     unit: "%",  dec: 0 },
  bees_on_board:   { label: "Abejas en la tabla",     short: "ACTIVIDAD",  unit: "",   dec: 1 },
  bees_in:         { label: "Entradas",               short: "ENTRAN",     unit: "",   dec: 0 },
  bees_out:        { label: "Salidas",                short: "SALEN",      unit: "",   dec: 0 },
  accel_x:         { label: "Aceleración X",          short: "ACEL. X",    unit: "g",  dec: 2 },
  accel_y:         { label: "Aceleración Y",          short: "ACEL. Y",    unit: "g",  dec: 2 },
  accel_z:         { label: "Aceleración Z",          short: "ACEL. Z",    unit: "g",  dec: 2 },
};

// What monitoreo draws, in this order. `with` is the exterior line that shares
// the chart: the gap between the two is the diagnosis, not either line alone.
const CARDS = [
  { metric: "bees_on_board", sensor: "camera",     title: "ACTIVIDAD EN LA PIQUERA" },
  { metric: "temperature",   sensor: "thermo",     title: "TEMPERATURA", with: "temperature_out" },
  { metric: "humidity",      sensor: "thermo",     title: "HUMEDAD",     with: "humidity_out" },
  { metric: "accel_z",       sensor: "movement",   title: "MOVIMIENTO",  still: true },
];

let status = null;
let range = { start: "-1h", window: "1m" };
let metricRange = { start: "-1h", window: "1m" };
let openMetric = null;

const meta = (m) => METRICS[m] || { label: m, short: m, unit: "", dec: 1 };
const $ = (id) => document.getElementById(id);

function fmt(metric, value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const m = meta(metric);
  // Spanish writes decimals with a comma.
  return Number(value).toFixed(m.dec).replace(".", ",");
}

function unitOf(metric) {
  return meta(metric).unit;
}

function clock(ts) {
  const d = new Date(ts);
  const p = (n) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}`;
}

function dayClock(ts) {
  const d = new Date(ts);
  const months = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"];
  return `${d.getDate()} ${months[d.getMonth()]} · ${clock(ts)}`;
}

function value(metric) {
  return status && status.latest[metric] ? status.latest[metric].value : null;
}

// --- gráfica --------------------------------------------------------------
// Hand-drawn SVG. The box has no internet, so a charting library would have to
// be bundled, and this draws one or two lines.

function chart(seriesIn, seriesOut, metric) {
  const W = 354, H = 104, L = 6, R = 6, T = 10, B = 18;

  if (!seriesIn.length && !seriesOut.length) {
    return `<svg viewBox="0 0 ${W} ${H}" class="chart">
      <text x="${W / 2}" y="${H / 2}" class="nodata">sin datos en este rango</text></svg>`;
  }

  const all = seriesIn.concat(seriesOut);
  const xs = all.map((p) => new Date(p.ts).getTime());
  let lo = Math.min(...all.map((p) => p.value));
  let hi = Math.max(...all.map((p) => p.value));

  const band = meta(metric).band;
  if (band) { lo = Math.min(lo, band[0] - 0.5); hi = Math.max(hi, band[1] + 0.5); }
  if (hi - lo < 1e-6) { lo -= 1; hi += 1; }
  const pad = (hi - lo) * 0.12;
  lo -= pad; hi += pad;

  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  const px = (t) => L + ((t - x0) / (x1 - x0 || 1)) * (W - L - R);
  const py = (v) => H - B - ((v - lo) / (hi - lo)) * (H - T - B);

  const path = (pts) => pts.map((p, i) =>
    `${i ? "L" : "M"}${px(new Date(p.ts).getTime()).toFixed(1)},${py(p.value).toFixed(1)}`
  ).join(" ");

  let out = `<svg viewBox="0 0 ${W} ${H}" class="chart">`;
  // The healthy band for brood temperature: the alarm is the line leaving it.
  if (band) {
    out += `<rect x="${L}" y="${py(band[1]).toFixed(1)}" width="${W - L - R}"
             height="${(py(band[0]) - py(band[1])).toFixed(1)}" class="band"/>`;
  }
  out += `<line x1="${L}" y1="${H - B}" x2="${W - R}" y2="${H - B}" class="grid"/>`;
  if (seriesOut.length) out += `<path d="${path(seriesOut)}" class="out"/>`;
  if (seriesIn.length) out += `<path d="${path(seriesIn)}" class="in"/>`;
  out += `<text x="${L}" y="${H - 5}" class="tick">${clock(x0)}</text>`;
  out += `<text x="${W - R}" y="${H - 5}" class="tick" text-anchor="end">${clock(x1)}</text>`;
  out += `<text x="${L}" y="${T + 2}" class="tick">${fmt(metric, hi)}</text>`;
  out += `</svg>`;
  return out;
}

async function history(metric, r) {
  try {
    const res = await fetch(api(`/api/history/${metric}/${r.start}/${r.window}`));
    return await res.json();
  } catch (err) {
    return [];
  }
}

// --- monitoreo ------------------------------------------------------------

function sensorOf(name) {
  return status && status.sensors[name] ? status.sensors[name] : null;
}

async function renderCards() {
  const root = $("cards");
  root.innerHTML = "";

  for (const card of CARDS) {
    const sensor = sensorOf(card.sensor);
    // Absent means never seen: draw nothing at all rather than an empty card.
    if (!sensor || sensor.state === "absent") continue;

    const el = document.createElement("button");
    el.className = "card" + (sensor.state === "stale" ? " quiet" : "");
    el.dataset.metric = card.metric;

    const stale = sensor.state === "stale"
      ? `<div class="note" style="color:var(--red)">SIN RESPUESTA DESDE LAS ${clock(sensor.last_seen)}</div>` : "";
    const tag = sensor.simulated ? `<span class="tag">SIMULADO</span>` : "";

    let extra = "";
    if (card.with) {
      extra = `<span class="unit">${unitOf(card.metric)}</span>
               <span class="grow"></span>
               <span class="name">FUERA</span>
               <span class="now" style="font-size:18px">${fmt(card.with, value(card.with))}</span>
               <span class="unit">${unitOf(card.with)}</span>`;
    } else {
      extra = `<span class="unit">${unitOf(card.metric)}</span><span class="grow"></span>`;
    }

    el.innerHTML = `
      <div class="head">
        <span class="name">${card.title}</span>${tag}
        <span class="grow"></span>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
          <path d="M9.5 5 16.5 12l-7 7" stroke="#3a3834" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      <div class="head">
        <span class="now warm" id="live-${card.metric}">${fmt(card.metric, value(card.metric))}</span>
        ${extra}
      </div>
      ${stale}
      <div class="slot"></div>`;

    root.appendChild(el);

    if (card.still) {
      el.querySelector(".slot").innerHTML =
        `<div class="note">${describeStillness()}</div>`;
      continue;
    }

    const [a, b] = await Promise.all([
      history(card.metric, range),
      card.with ? history(card.with, range) : Promise.resolve([]),
    ]);
    el.querySelector(".slot").innerHTML =
      chart(a, b, card.metric) + (card.with ? legend(card) : "");
  }
}

function legend(card) {
  return `<div class="legend">
    <span><i style="background:var(--yell)"></i>DENTRO</span>
    <span><i style="background:var(--cool)"></i>FUERA</span>
    ${meta(card.metric).band ? `<span><i style="background:#16150f;height:8px"></i>34-35 °C SANO</span>` : ""}
  </div>`;
}

function describeStillness() {
  const s = sensorOf("movement");
  if (!s || s.state !== "present") return "";
  const shaken = (status.events || []).find((e) => e.kind === "movement");
  return shaken
    ? `QUIETA · ÚLTIMA SACUDIDA ${dayClock(shaken.ts)}`
    : "QUIETA · NINGUNA SACUDIDA REGISTRADA";
}

// --- avisos ---------------------------------------------------------------

function renderVerdict(events) {
  const box = $("verdict");
  const open = events.filter((e) => !e.seen);
  const bad = open.some((e) => e.severity === "alert");

  box.className = "verdict" + (bad ? " bad" : "");
  if (!events.length) {
    $("verdict-title").textContent = "TODO EN ORDEN";
    $("verdict-note").textContent = "Ningún aviso desde que la caja está en marcha.";
  } else if (open.length) {
    $("verdict-title").textContent = open.length === 1 ? "1 AVISO" : `${open.length} AVISOS`;
    $("verdict-note").textContent = "Sin revisar. La caja no dice la causa; ven a mirar.";
  } else {
    $("verdict-title").textContent = "TODO REVISADO";
    $("verdict-note").textContent = `${events.length} aviso${events.length > 1 ? "s" : ""} en el historial.`;
  }
}

function renderEvents(events) {
  const root = $("events");
  root.innerHTML = "";
  $("events-empty").hidden = events.length > 0;

  for (const e of events) {
    const el = document.createElement("button");
    el.className = "event" + (e.severity === "warn" ? " warn" : "") + (e.seen ? " seen" : "");
    el.dataset.event = e.id;
    const shot = e.photo
      ? `<img class="shot" src="${e.photo}" alt="Foto del momento del aviso">`
      : `<div class="shot"></div>`;
    el.innerHTML = `${shot}
      <div class="body">
        <div class="when">${dayClock(e.ts)}</div>
        <div class="what">${e.title}</div>
        <div class="why">${e.detail}</div>
      </div>`;
    root.appendChild(el);
  }
}

async function loadEvents() {
  try {
    const res = await fetch(api("/api/events"));
    status.events = await res.json();
  } catch (err) {
    status.events = [];
  }
  renderVerdict(status.events);
  renderEvents(status.events);
}

function openEvent(id) {
  const e = (status.events || []).find((x) => String(x.id) === String(id));
  if (!e) return;

  $("event-detail").innerHTML = `
    ${e.photo ? `<div class="camera"><div class="frame">
       <img src="${e.photo}" alt="Foto guardada en el momento del aviso">
       <div class="over">${dayClock(e.ts)}</div></div></div>` : ""}
    <div class="readout">
      <div class="big" style="font-size:21px;color:var(--${e.severity === "warn" ? "yell" : "red"})">${e.title}</div>
      <div class="sub" style="font-size:13px;color:var(--ink);line-height:1.6">${e.detail}</div>
    </div>
    <div class="rows">
      <div class="row"><div class="k">Cría</div><div class="grow"></div>
        <div class="v">${fmt("temperature", value("temperature"))} °C</div></div>
      <div class="row"><div class="k">Exterior</div><div class="grow"></div>
        <div class="v">${fmt("temperature_out", value("temperature_out"))} °C</div></div>
      <div class="row"><div class="k">Abejas en la tabla</div><div class="grow"></div>
        <div class="v">${fmt("bees_on_board", value("bees_on_board"))}</div></div>
    </div>`;

  push("view-event");
  if (!e.seen) {
    fetch(api(`/api/events/${e.id}/seen`), { method: "POST" })
      .then(() => refresh())
      .catch(() => {});
  }
}

// --- detalle de métrica ---------------------------------------------------

async function openMetricView(metric) {
  openMetric = metric;
  const m = meta(metric);
  const card = CARDS.find((c) => c.metric === metric);
  const sensor = card ? sensorOf(card.sensor) : null;

  $("metric-title").textContent = m.label.toUpperCase();
  $("metric-tag").textContent = sensor && sensor.simulated ? "SIMULADO" : "";
  $("metric-now").textContent = `${fmt(metric, value(metric))} ${m.unit}`.trim();
  $("metric-sub").textContent = status.latest[metric]
    ? `ÚLTIMA LECTURA ${clock(status.latest[metric].ts)}` : "SIN LECTURAS";

  push("view-metric");
  await drawMetricChart();
}

async function drawMetricChart() {
  if (!openMetric) return;
  const card = CARDS.find((c) => c.metric === openMetric);
  const pair = card && card.with;

  $("metric-chart").innerHTML = `<div class="card" style="border:0"><div class="note">cargando…</div></div>`;

  const [a, b] = await Promise.all([
    history(openMetric, metricRange),
    pair ? history(pair, metricRange) : Promise.resolve([]),
  ]);

  $("metric-chart").innerHTML =
    `<div style="padding:0 16px 8px">${chart(a, b, openMetric)}${pair ? legend(card) : ""}</div>`;

  const vals = a.map((p) => p.value);
  $("metric-rows").innerHTML = vals.length ? `
    <div class="row"><div class="k">Mínimo</div><div class="grow"></div>
      <div class="v">${fmt(openMetric, Math.min(...vals))} ${meta(openMetric).unit}</div></div>
    <div class="row"><div class="k">Máximo</div><div class="grow"></div>
      <div class="v">${fmt(openMetric, Math.max(...vals))} ${meta(openMetric).unit}</div></div>
    <div class="row"><div class="k">Media</div><div class="grow"></div>
      <div class="v">${fmt(openMetric, vals.reduce((s, v) => s + v, 0) / vals.length)} ${meta(openMetric).unit}</div></div>
    <div class="row"><div class="k">Muestras</div><div class="grow"></div>
      <div class="v">${vals.length}</div></div>` : "";
}

// --- navegación -----------------------------------------------------------

function push(id) { $(id).hidden = false; window.scrollTo(0, 0); }
function pop(id) { $(id).hidden = true; if (id === "view-live") $("live-video").pause(); }

function showTab(which) {
  const avisos = which === "avisos";
  $("tab-avisos").setAttribute("aria-selected", String(avisos));
  $("tab-monitor").setAttribute("aria-selected", String(!avisos));
  $("view-avisos").hidden = !avisos;
  $("view-monitor").hidden = avisos;
}

// --- estado ---------------------------------------------------------------

async function refresh() {
  const res = await fetch(api("/api/status"));
  const events = status ? status.events : [];
  status = await res.json();
  status.events = events || [];

  $("hive").textContent = status.hive;
  $("clock-warning").hidden = status.clock_ok;

  const badge = $("pending");
  badge.hidden = !status.pending;
  badge.textContent = status.pending;

  $("camera-still").src = `media/frames/${String(Math.floor((Date.now() / 10000) % 12)).padStart(2, "0")}.jpg`;
  const cam = sensorOf("camera");
  $("camera-over").textContent = cam && cam.simulated ? "PIQUERA · CLIP SIMULADO" : "PIQUERA";

  await renderCards();
}

// Live values replace the number in place, without a re-render.
for (const metric of Object.keys(METRICS)) {
  socket.on(metric, (msg) => {
    if (status) status.latest[metric] = msg;
    const el = $(`live-${metric}`);
    if (el) el.textContent = fmt(metric, msg.value);
    if (metric === "bees_on_board") $("live-board").textContent = fmt(metric, msg.value);
    if (metric === "bees_in") $("live-in").textContent = fmt(metric, msg.value * 60);
    if (metric === "bees_out") $("live-out").textContent = fmt(metric, msg.value * 60);
  });
}

socket.on("sensors", () => refresh());
socket.on("event", () => loadEvents().then(refresh));

// --- enganches ------------------------------------------------------------

$("tab-avisos").addEventListener("click", () => showTab("avisos"));
$("tab-monitor").addEventListener("click", () => showTab("monitor"));

$("ranges").addEventListener("click", (ev) => {
  const btn = ev.target.closest("button");
  if (!btn) return;
  [...$("ranges").children].forEach((b) => b.setAttribute("aria-pressed", String(b === btn)));
  range = { start: btn.dataset.start, window: btn.dataset.window };
  renderCards();
});

$("metric-ranges").addEventListener("click", (ev) => {
  const btn = ev.target.closest("button");
  if (!btn) return;
  [...$("metric-ranges").children].forEach((b) => b.setAttribute("aria-pressed", String(b === btn)));
  metricRange = { start: btn.dataset.start, window: btn.dataset.window };
  drawMetricChart();
});

$("cards").addEventListener("click", (ev) => {
  const card = ev.target.closest(".card");
  if (card && card.dataset.metric) openMetricView(card.dataset.metric);
});

$("events").addEventListener("click", (ev) => {
  const row = ev.target.closest(".event");
  if (row) openEvent(row.dataset.event);
});

$("go-live").addEventListener("click", () => {
  push("view-live");
  const v = $("live-video");
  // The clip loops on the server's clock, so start where the counters are.
  v.currentTime = (Date.now() / 1000) % 120;
  v.play().catch(() => {});
});

document.querySelectorAll("[data-close]").forEach((btn) => {
  btn.addEventListener("click", () => pop(btn.dataset.close));
});

// --- arranque -------------------------------------------------------------

refresh().then(loadEvents);

// A sensor going quiet is not an event anyone sends us, so poll for it.
setInterval(refresh, 15000);
