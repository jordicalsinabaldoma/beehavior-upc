#!/usr/bin/env python3
"""
Build the page the device serves over its own WiFi, the one the beekeeper
opens on the phone when arriving at the apiary.

Self-contained HTML: no external CSS, JS or fonts, because in the apiary
there is no internet. Charts are inline SVG built from the real CSV output.
"""
import argparse
import csv
import html
from datetime import datetime
from pathlib import Path


def read_rows(p):
    with open(p) as f:
        return [{k: float(v) if k != "t_s" else float(v) for k, v in r.items()}
                for r in csv.DictReader(f)]


def read_events(p):
    if not Path(p).exists():
        return []
    with open(p) as f:
        return list(csv.DictReader(f))


def sparkline_svg(values, w=640, h=140, color="#e0a83c", fill="#e0a83c22"):
    if len(values) < 2:
        return ""
    vmax = max(max(values), 1.0)
    pad = 8
    pts = []
    for i, v in enumerate(values):
        x = pad + i * (w - 2 * pad) / (len(values) - 1)
        y = h - pad - (v / vmax) * (h - 2 * pad - 14)
        pts.append((x, y))
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{pad},{h-pad} " + line + f" {pts[-1][0]:.1f},{h-pad}"
    grid = "".join(
        f'<line x1="{pad}" y1="{h-pad-(k/4)*(h-2*pad-14):.1f}" x2="{w-pad}" '
        f'y2="{h-pad-(k/4)*(h-2*pad-14):.1f}" stroke="#2e2822" stroke-width="1"/>'
        for k in range(5))
    return (f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" class="spark">'
            f'{grid}<polygon points="{area}" fill="{fill}"/>'
            f'<polyline points="{line}" fill="none" stroke="{color}" stroke-width="2.5" '
            f'stroke-linejoin="round"/>'
            f'<text x="{pad+2}" y="{pad+10}" fill="#8a8279" font-size="11">'
            f'max {vmax:.0f}</text></svg>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--events", default=None)
    ap.add_argument("--hive", default="Colmena 01")
    ap.add_argument("-o", "--out", default="out/panel_apicultor.html")
    args = ap.parse_args()

    rows = read_rows(args.csv)
    events = read_events(args.events) if args.events else []
    act = [r["bees_on_board"] for r in rows]
    n_in = int(rows[-1]["in_total"]) if rows else 0
    n_out = int(rows[-1]["out_total"]) if rows else 0
    n_intr = int(rows[-1]["intruder_events"]) if rows else 0
    dur = rows[-1]["t_s"] if rows else 0
    peak = max(act) if act else 0

    if n_intr:
        status, scls, smsg = "AVISO", "warn", f"{n_intr} deteccion(es) de algo que no es una abeja"
    elif peak < 1:
        status, scls, smsg = "REVISAR", "warn", "actividad practicamente nula en la piquera"
    else:
        status, scls, smsg = "NORMAL", "ok", "actividad dentro de lo esperado"

    ev_rows = ""
    for e in events[-40:][::-1]:
        kind = e["kind"]
        lbl = {"IN": "entra", "OUT": "sale"}.get(kind, "INTRUSO")
        cls = {"IN": "e-in", "OUT": "e-out"}.get(kind, "e-alert")
        tid = f'#{e["track"]}' if int(e["track"]) > 0 else ""
        ev_rows += (f'<tr><td class="t">{float(e["t_s"]):.1f} s</td>'
                    f'<td class="{cls}">{lbl}</td><td class="id">{tid}</td></tr>')

    doc = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Beehaviour · {html.escape(args.hive)}</title>
<style>
:root{{color-scheme:dark}}
*{{box-sizing:border-box}}
body{{margin:0;background:#16120e;color:#eee;
 font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
.wrap{{max-width:760px;margin:0 auto;padding:16px}}
header{{display:flex;align-items:baseline;justify-content:space-between;gap:12px;flex-wrap:wrap}}
h1{{font-size:22px;margin:0;letter-spacing:.5px}}
.sub{{color:#8a8279;font-size:13px}}
.status{{margin:14px 0;padding:14px 16px;border-radius:12px;display:flex;
 align-items:center;gap:12px}}
.status.ok{{background:#16301c;border:1px solid #2f6b3c}}
.status.warn{{background:#331a16;border:1px solid #8a3b2c}}
.dot{{width:10px;height:10px;border-radius:50%;flex:none}}
.ok .dot{{background:#5ac85a}} .warn .dot{{background:#e0503c}}
.status b{{letter-spacing:1px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:12px 0}}
.card{{background:#221c17;border-radius:12px;padding:14px 16px}}
.card .k{{color:#8a8279;font-size:12px;letter-spacing:.6px;text-transform:uppercase}}
.card .v{{font-size:30px;font-weight:600;margin-top:4px}}
.v.in{{color:#5ac85a}} .v.out{{color:#f0a05a}} .v.alert{{color:#e0503c}}
section{{background:#221c17;border-radius:12px;padding:14px 16px;margin:12px 0}}
section h2{{font-size:13px;color:#8a8279;letter-spacing:.8px;text-transform:uppercase;margin:0 0 10px}}
.spark{{width:100%;height:140px;display:block}}
table{{width:100%;border-collapse:collapse;font-size:14px}}
td{{padding:6px 4px;border-bottom:1px solid #2e2822}}
td.t{{color:#8a8279;width:74px}} td.id{{color:#6e675f;text-align:right}}
.e-in{{color:#5ac85a}} .e-out{{color:#f0a05a}} .e-alert{{color:#e0503c;font-weight:600}}
.scroll{{max-height:280px;overflow:auto}}
.pending{{border:1px dashed #4a4038;background:none;color:#8a8279}}
footer{{color:#6e675f;font-size:12px;margin:20px 0 8px;line-height:1.7}}
</style></head><body><div class="wrap">
<header>
  <h1>🐝 {html.escape(args.hive)}</h1>
  <span class="sub">sincronizado por WiFi local · {datetime.now():%d/%m/%Y %H:%M}</span>
</header>

<div class="status {scls}"><span class="dot"></span>
  <div><b>{status}</b><div class="sub">{smsg}</div></div></div>

<div class="grid">
  <div class="card"><div class="k">Entradas</div><div class="v in">{n_in}</div></div>
  <div class="card"><div class="k">Salidas</div><div class="v out">{n_out}</div></div>
  <div class="card"><div class="k">Pico en la tabla</div><div class="v">{peak:.0f}</div></div>
  <div class="card"><div class="k">Intrusos</div>
    <div class="v {'alert' if n_intr else ''}">{n_intr}</div></div>
</div>

<section><h2>Actividad en la piquera</h2>
  {sparkline_svg(act)}
  <div class="sub">abejas en la tabla de vuelo, promedio por segundo · {dur:.0f} s observados</div>
</section>

<section><h2>Eventos</h2><div class="scroll"><table>{ev_rows}</table></div></section>

<section class="pending"><h2>Temperatura y humedad</h2>
  Pendiente de conectar los dos sensores Modulino Thermo.
  Compararan la temperatura del nido de cria con la exterior para detectar
  colonia huerfana o enjambrazon proxima.
</section>

<section class="pending"><h2>Movimiento de la colmena</h2>
  Pendiente de conectar el Modulino Movement, para avisar de robo o vuelco.
</section>

<footer>
  Los datos de esta pagina salen del analisis de video real procesado en el
  dispositivo. Nada se envia a internet.<br>
  Beehaviour · prueba de concepto
</footer>
</div></body></html>"""

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(doc)
    print(f"{args.out}  ({len(rows)} s de datos, {len(events)} eventos)")


if __name__ == "__main__":
    main()
