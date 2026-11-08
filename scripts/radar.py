"""Radar de productos para vender en Mercado Libre.
Recorre los "Más vendidos" de subcategorías, mira cuántos vendedores compiten en cada
producto y a qué precios, y genera data/radar.csv + data/radar.md con un puntaje de oportunidad.
Usa la misma autorización que el actualizador (data/token.enc)."""
import csv, json, statistics, time, datetime as dt
from update import http, get_token, API, SITE, ROOT

# Rubros aptos para empezar con poco stock (se excluyen alimentos, autos, inmuebles, servicios, etc.)
RAICES = {
    "MLA1574": "Hogar, Muebles y Jardín", "MLA407134": "Herramientas", "MLA1000": "Electrónica, Audio y Video",
    "MLA1051": "Celulares y Teléfonos", "MLA1648": "Computación", "MLA1276": "Deportes y Fitness",
    "MLA1246": "Belleza y Cuidado Personal", "MLA1071": "Animales y Mascotas", "MLA1384": "Bebés",
    "MLA1132": "Juegos y Juguetes", "MLA1747": "Accesorios para Vehículos", "MLA5726": "Electrodomésticos",
    "MLA1430": "Ropa y Accesorios", "MLA409431": "Salud y Equipamiento Médico", "MLA1144": "Consolas y Videojuegos",
    "MLA1500": "Construcción", "MLA1499": "Industrias y Oficinas", "MLA1182": "Instrumentos Musicales",
}
TOP_POR_SUBCAT = 5
MAX_PRODUCTOS = 1200
GENERICAS = {"genérica", "generica", "genérico", "generico", "sin marca", "otra", "otras", "importada", "no aplica"}
EXCLUIR = ("tarjeta de regalo", "gift card", "robux", "giftcard", "suscripción", "licencia")
PRECIO_MIN, PRECIO_MAX = 8000, 150000   # rango de precio de venta apto para una prueba chica (ARS)

def main():
    token = get_token()
    subcats = []
    for cid, name in RAICES.items():
        try:
            c = http("GET", f"{API}/categories/{cid}", token=token)
            for ch in c.get("children_categories", []):
                subcats.append((ch["id"], ch["name"], name))
        except RuntimeError as e:
            print("cat:", cid, str(e)[:100])
        time.sleep(0.2)
    print("subcategorías:", len(subcats))
    found = {}
    for sid, sname, root in subcats:
        try:
            h = http("GET", f"{API}/highlights/{SITE}/category/{sid}", token=token)
        except RuntimeError:
            continue
        for el in h.get("content", [])[:TOP_POR_SUBCAT]:
            if el.get("type") == "PRODUCT" and el["id"] not in found:
                found[el["id"]] = {"pos": el.get("position", 99), "sub": sname, "root": root}
        time.sleep(0.15)
        if len(found) >= MAX_PRODUCTOS: break
    print("productos en ranking:", len(found))
    rows = []
    for pid, meta in found.items():
        try:
            p = http("GET", f"{API}/products/{pid}", token=token)
            r = http("GET", f"{API}/products/{pid}/items?limit=50", token=token)
        except RuntimeError as e:
            print("prod:", pid, str(e)[:80]); continue
        name = p.get("name") or ""
        if any(w in name.lower() for w in EXCLUIR): continue
        brand = next((a.get("value_name") for a in p.get("attributes", []) if a.get("id") == "BRAND"), "") or ""
        generico = brand.strip().lower() in GENERICAS or not brand
        items = [x for x in r.get("results", []) if x.get("price") and x.get("condition", "new") == "new"]
        if not items: continue
        total_sellers = (r.get("paging") or {}).get("total", len(items))
        prices = sorted(x["price"] for x in items)
        free = [x for x in items if (x.get("shipping") or {}).get("free_shipping")]
        full = [x for x in items if (x.get("shipping") or {}).get("logistic_type") == "fulfillment"]
        official = [x for x in items if x.get("official_store_id")]
        ref_price = min(x["price"] for x in free) if free else prices[0]
        med = statistics.median(prices)
        # Puntaje 0-100: demanda (puesto en el ranking), poca competencia, precio en rango, sin tienda oficial dominante
        demanda = max(0, 10 - meta["pos"]) / 9
        competencia = 1 / (1 + max(0, total_sellers - 3) / 8)
        en_rango = 1 if PRECIO_MIN <= ref_price <= PRECIO_MAX else 0.3
        sin_oficial = 0.6 if official else 1
        score = round(100 * (0.45 * demanda + 0.55 * competencia) * en_rango * sin_oficial * (1 if generico else 0.7))
        rows.append({
            "puntaje": score, "producto": name, "marca": brand or "Sin marca", "generico": "Sí" if generico else "No", "rubro": meta["root"], "subcategoria": meta["sub"],
            "puesto_ranking": meta["pos"], "vendedores": total_sellers, "precio_ref": round(ref_price),
            "precio_min": round(prices[0]), "precio_mediana": round(med), "dispersion_%": round((med - prices[0]) / med * 100) if med else 0,
            "con_envio_gratis": len(free), "en_full": len(full), "tienda_oficial": "Sí" if official else "No",
            "id": pid, "enlace": f"https://www.mercadolibre.com.ar/p/{pid}",
        })
        time.sleep(0.15)
    rows.sort(key=lambda r: -r["puntaje"])
    out = ROOT / "data" / "radar.csv"
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["puntaje"], delimiter=";")
        w.writeheader(); w.writerows(rows)
    hoy = dt.datetime.now().strftime("%d/%m/%Y")
    md = [f"# Radar de productos – {hoy}", "", f"{len(rows)} productos analizados de {len(subcats)} subcategorías. Top 30 por puntaje:", "",
          "| # | Puntaje | Producto | Marca | Rubro | Puesto | Vendedores | Precio ref. |", "|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows[:30], 1):
        md.append(f"| {i} | {r['puntaje']} | [{r['producto'][:60]}]({r['enlace']}) | {r['marca'][:20]} | {r['rubro']} | {r['puesto_ranking']} | {r['vendedores']} | $ {r['precio_ref']:,} |".replace(",", "."))
    (ROOT / "data" / "radar.md").write_text("\n".join(md), encoding="utf-8")
    print("radar listo:", len(rows))

if __name__ == "__main__":
    main()
