"""Historial de tendencias: guarda una foto diaria del ranking y de las búsquedas más populares
y arma resúmenes con qué sube, qué baja y qué es nuevo."""
import csv, datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"
HIST_P, HIST_B = D / "tendencias_historial.csv", D / "busquedas_historial.csv"
RES_P, RES_B = D / "tendencias_productos.csv", D / "tendencias_busquedas.csv"

def _read(p):
    if not p.exists(): return []
    with p.open(encoding="utf-8") as f: return list(csv.DictReader(f, delimiter=";"))

def _append(p, fields, rows):
    new = not p.exists()
    with p.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        if new: w.writeheader()
        w.writerows(rows)

def _write(p, fields, rows):
    with p.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=";"); w.writeheader(); w.writerows(rows)

def guardar(hoy, productos, terminos):
    """productos: dicts con id, name, cat, pos, price. terminos: lista de strings ordenada. Una foto por día."""
    if not any(r["fecha"] == hoy for r in _read(HIST_P)):
        _append(HIST_P, ["fecha", "id", "producto", "rubro", "puesto", "precio"],
                [{"fecha": hoy, "id": p["id"], "producto": p["name"], "rubro": p["cat"], "puesto": p["pos"], "precio": round(p["price"])} for p in productos])
    if terminos and not any(r["fecha"] == hoy for r in _read(HIST_B)):
        _append(HIST_B, ["fecha", "puesto", "termino"], [{"fecha": hoy, "puesto": i, "termino": t} for i, t in enumerate(terminos, 1)])
    resumir(hoy)

def _estado(hoy_pos, ant_pos):
    if ant_pos is None: return "Nuevo"
    if hoy_pos < ant_pos: return "Sube"
    if hoy_pos > ant_pos: return "Baja"
    return "Igual"

def resumir(hoy):
    ref = (dt.date.fromisoformat(hoy) - dt.timedelta(days=7)).isoformat()
    # Productos
    hp = _read(HIST_P); fechas = sorted({r["fecha"] for r in hp})
    if fechas:
        ant_f = max([f for f in fechas if f <= ref] or [fechas[0]])
        hoy_rows = [r for r in hp if r["fecha"] == hoy] or [r for r in hp if r["fecha"] == fechas[-1]]
        ant = {r["id"]: r for r in hp if r["fecha"] == ant_f}
        dias = {}
        for r in hp: dias.setdefault(r["id"], set()).add(r["fecha"])
        out = []
        for r in hoy_rows:
            a = ant.get(r["id"]) if ant_f != r["fecha"] else None
            pa = int(a["puesto"]) if a else None
            out.append({"producto": r["producto"], "rubro": r["rubro"], "estado": _estado(int(r["puesto"]), pa),
                        "puesto_hoy": r["puesto"], "puesto_hace_7_dias": pa if pa else "", "dias_en_top": len(dias[r["id"]]),
                        "precio_hoy": r["precio"], "precio_hace_7_dias": a["precio"] if a else "",
                        "var_precio_%": round((float(r["precio"]) / float(a["precio"]) - 1) * 100, 1) if a and float(a["precio"]) else "",
                        "id": r["id"], "enlace": f"https://www.mercadolibre.com.ar/p/{r['id']}"})
        orden = {"Nuevo": 0, "Sube": 1, "Igual": 2, "Baja": 3}
        out.sort(key=lambda x: (orden[x["estado"]], int(x["puesto_hoy"])))
        _write(RES_P, list(out[0].keys()) if out else ["producto"], out)
    # Búsquedas
    hb = _read(HIST_B); fb = sorted({r["fecha"] for r in hb})
    if fb:
        ant_f = max([f for f in fb if f <= ref] or [fb[0]])
        hoy_f = fb[-1]
        ant = {r["termino"]: int(r["puesto"]) for r in hb if r["fecha"] == ant_f} if ant_f != hoy_f else {}
        dias = {}
        for r in hb: dias.setdefault(r["termino"], set()).add(r["fecha"])
        out = []
        for r in [r for r in hb if r["fecha"] == hoy_f]:
            pa = ant.get(r["termino"])
            out.append({"termino": r["termino"], "estado": _estado(int(r["puesto"]), pa) if ant else "Nuevo",
                        "puesto_hoy": r["puesto"], "puesto_hace_7_dias": pa or "", "dias_en_top": len(dias[r["termino"]]),
                        "buscar_en_ml": "https://listado.mercadolibre.com.ar/" + r["termino"].replace(" ", "-")})
        _write(RES_B, list(out[0].keys()), out)
