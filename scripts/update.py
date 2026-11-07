"""Ojo al Precio - actualizador.
Cada ejecución: pide un token a Mercado Libre, lee los "Más vendidos" de cada
categoría, guarda el historial de precios y genera docs/data.json para la web.
Variables de entorno (secretos de GitHub): ML_CLIENT_ID, ML_CLIENT_SECRET.
Opcional: ML_REFRESH_TOKEN (si el modo client_credentials no alcanza).
"""
import json, os, sys, time, statistics, datetime as dt
from pathlib import Path
import urllib.request, urllib.parse, urllib.error

API = "https://api.mercadolibre.com"
SITE = "MLA"
ROOT = Path(__file__).resolve().parent.parent
HIST = ROOT / "data" / "history.json"
LINKS = ROOT / "data" / "links.json"       # enlaces meli.la cargados a mano (modo manual)
OUT = ROOT / "docs" / "data.json"
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
MOCK = "--mock" in sys.argv

def http(method, url, data=None, token=None):
    headers = {"Accept": "application/json", "User-Agent": "ojoalprecio-bot/1.0"}
    if token: headers["Authorization"] = f"Bearer {token}"
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 2:
                time.sleep(3 * (attempt + 1)); continue
            msg = e.read().decode(errors="ignore")[:200]
            raise RuntimeError(f"{e.code} {url} {msg}")
        except urllib.error.URLError:
            if attempt < 2: time.sleep(3); continue
            raise

def get_token():
    cid, sec = os.environ.get("ML_CLIENT_ID"), os.environ.get("ML_CLIENT_SECRET")
    if not cid or not sec:
        sys.exit("Faltan los secretos ML_CLIENT_ID y ML_CLIENT_SECRET")
    rt = os.environ.get("ML_REFRESH_TOKEN")
    if rt:
        r = http("POST", f"{API}/oauth/token", {"grant_type": "refresh_token", "client_id": cid, "client_secret": sec, "refresh_token": rt})
    else:
        r = http("POST", f"{API}/oauth/token", {"grant_type": "client_credentials", "client_id": cid, "client_secret": sec})
    return r["access_token"]

def chunks(lst, n):
    for i in range(0, len(lst), n): yield lst[i:i + n]

def affiliate(permalink, pid, links):
    if pid in links: return links[pid]
    if CFG.get("affiliate_mode") == "params" and permalink:
        base = permalink.split("#")[0].split("?")[0]
        return f"{base}?matt_word={CFG['matt_word']}&matt_tool={CFG['matt_tool']}"
    return permalink

def fetch(token):
    cats = http("GET", f"{API}/sites/{SITE}/categories", token=token)
    skip = set(CFG.get("skip_categories", []))
    found = []
    for c in cats:
        if c["id"] in skip or c["name"] in skip: continue
        try:
            h = http("GET", f"{API}/highlights/{SITE}/category/{c['id']}", token=token)
        except RuntimeError as e:
            print("sin ranking:", c["name"], e); continue
        for el in h.get("content", [])[: CFG["top_per_category"]]:
            found.append({"id": el["id"], "type": el.get("type", "ITEM"), "pos": el.get("position", 99), "cat": c["name"]})
        time.sleep(0.3)
    out = []
    items = [f for f in found if f["type"] == "ITEM"]
    for grp in chunks(items, 20):
        try:
            res = http("GET", f"{API}/items?ids={','.join(g['id'] for g in grp)}&attributes=id,title,price,original_price,secure_thumbnail,thumbnail,permalink", token=token)
        except RuntimeError as e:
            print("items:", e); continue
        meta = {g["id"]: g for g in grp}
        for r in res:
            b = r.get("body") or {}
            if r.get("code") != 200 or not b.get("price"): continue
            m = meta[b["id"]]
            out.append({"id": b["id"], "name": b["title"], "price": b["price"], "list": b.get("original_price"),
                        "img": (b.get("secure_thumbnail") or b.get("thumbnail") or "").replace("-I.jpg", "-O.jpg"),
                        "permalink": b.get("permalink"), "cat": m["cat"], "pos": m["pos"]})
    for f in [f for f in found if f["type"] == "PRODUCT"]:
        try:
            p = http("GET", f"{API}/products/{f['id']}", token=token)
        except RuntimeError as e:
            print("product:", e); continue
        bb = p.get("buy_box_winner") or {}
        price = bb.get("price")
        if not price: continue
        pics = p.get("pictures") or [{}]
        out.append({"id": f["id"], "name": p.get("name"), "price": price, "list": bb.get("original_price"),
                    "img": pics[0].get("url", ""), "permalink": p.get("permalink") or f"https://www.mercadolibre.com.ar/p/{f['id']}",
                    "cat": f["cat"], "pos": f["pos"]})
        time.sleep(0.2)
    return out

def mock():
    import random
    random.seed(int(time.time()) // 43200)
    names = [("Celulares y Teléfonos", "Celular Samsung Galaxy A16 128 GB"), ("Electrodomésticos", "Freidora de aire 5 L"),
             ("Herramientas", "Taladro percutor inalámbrico 20 V"), ("Electrónica, Audio y Video", "Auriculares inalámbricos"),
             ("Computación", "Monitor 24 pulgadas Full HD"), ("Deportes y Fitness", "Mancuernas ajustables 20 kg")]
    out = []
    for i, (c, n) in enumerate(names):
        base = random.choice([69999, 119999, 189999, 349999])
        price = round(base * random.uniform(0.7, 0.95), -2)
        out.append({"id": f"MLA-MOCK{i}", "name": n, "price": price, "list": base, "img": "", "permalink": "https://www.mercadolibre.com.ar/",
                    "cat": c, "pos": random.randint(1, 10)})
    return out

def main():
    now = dt.datetime.now(dt.timezone.utc)
    today = now.strftime("%Y-%m-%d")
    hist = json.loads(HIST.read_text(encoding="utf-8")) if HIST.exists() else {}
    links = json.loads(LINKS.read_text(encoding="utf-8")) if LINKS.exists() else {}
    prev = {}
    if OUT.exists():
        try: prev = {p["id"]: p["rank"] for p in json.loads(OUT.read_text(encoding="utf-8")).get("products", [])}
        except Exception: pass
    rows = mock() if MOCK else fetch(get_token())
    print(f"productos leídos: {len(rows)}")
    cutoff = (now - dt.timedelta(days=CFG["history_days"])).strftime("%Y-%m-%d")
    products = []
    for r in rows:
        h = hist.setdefault(r["id"], {})
        h[today] = min(r["price"], h.get(today, r["price"]))
        for d in [d for d in h if d < cutoff]: del h[d]
        past = [v for d, v in h.items() if d < today]
        was = r["list"] if r["list"] and r["list"] > r["price"] else None
        off = round((1 - r["price"] / was) * 100) if was else 0
        if len(past) < CFG["min_history_days"]:
            verdict, note = "new", "Empezamos a seguir su precio"
            if not was: continue
        else:
            low, med = min(past), statistics.median(past)
            if r["price"] < low * 0.99:
                verdict, note = "real", f"Precio más bajo en {len(past) + 1} días"
            elif r["price"] < med * 0.95:
                verdict, note = "real", f"Bajó {round((1 - r['price'] / med) * 100)} % frente a su precio habitual"
            elif was and was > max(past) * 1.05:
                verdict, note = "fake", "Subieron el precio de lista antes del descuento"
            elif was:
                verdict, note = "fake", "Cuesta lo mismo que los últimos días: el descuento es de cartel"
            else:
                continue
        if verdict != "fake" and off < CFG["min_discount"] and verdict != "real":
            continue
        products.append({"id": r["id"], "name": r["name"], "cat": r["cat"], "price": r["price"], "was": was, "off": off,
                         "img": r["img"], "link": affiliate(r["permalink"], r["id"], links), "pos": r["pos"],
                         "verdict": verdict, "note": note})
    order = {"real": 0, "new": 1, "fake": 2}
    products.sort(key=lambda p: (order[p["verdict"]], p["pos"], -p["off"]))
    products = products[: CFG["max_products"]]
    for i, p in enumerate(products, 1):
        p["rank"] = i
        p["move"] = "nuevo" if p["id"] not in prev else (prev[p["id"]] - i)
    HIST.parent.mkdir(exist_ok=True)
    HIST.write_text(json.dumps(hist, ensure_ascii=False), encoding="utf-8")
    OUT.write_text(json.dumps({"updated": now.isoformat(timespec="minutes"), "products": products}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"publicados: {len(products)}")

if __name__ == "__main__":
    main()
