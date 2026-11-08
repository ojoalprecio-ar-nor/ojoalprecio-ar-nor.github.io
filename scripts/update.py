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

TOKEN_FILE = ROOT / "data" / "token.enc"
REDIRECT = CFG.get("redirect_uri", "")

def _fernet(secret):
    import base64, hashlib
    from cryptography.fernet import Fernet
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(("ojoalprecio:" + secret).encode()).digest()))

def _save_refresh(secret, rt):
    TOKEN_FILE.write_bytes(_fernet(secret).encrypt(rt.encode()))

def get_token():
    """Token de usuario: la primera vez con el código de autorización (ML_AUTH_CODE);
    después con el refresh token guardado cifrado en data/token.enc (se renueva en cada uso)."""
    cid, sec = os.environ.get("ML_CLIENT_ID", "").strip(), os.environ.get("ML_CLIENT_SECRET", "").strip()
    if not cid or not sec:
        sys.exit("Faltan los secretos ML_CLIENT_ID y ML_CLIENT_SECRET")
    code = os.environ.get("ML_AUTH_CODE", "").strip()
    if code:
        r = http("POST", f"{API}/oauth/token", {"grant_type": "authorization_code", "client_id": cid,
                 "client_secret": sec, "code": code, "redirect_uri": REDIRECT})
    elif TOKEN_FILE.exists():
        rt = _fernet(sec).decrypt(TOKEN_FILE.read_bytes()).decode()
        r = http("POST", f"{API}/oauth/token", {"grant_type": "refresh_token", "client_id": cid,
                 "client_secret": sec, "refresh_token": rt})
    else:
        sys.exit("Falta autorizar la app: ejecutá el workflow con el código de autorización (ver README).")
    if r.get("refresh_token"):
        _save_refresh(sec, r["refresh_token"])
    else:
        print("aviso: Mercado Libre no devolvió refresh_token (¿falta marcar Refresh Token / offline_access en la app?)")
    return r["access_token"]


CATS_FIJAS = {
    "MLA1051": "Celulares y Teléfonos", "MLA1648": "Computación", "MLA1000": "Electrónica, Audio y Video",
    "MLA5726": "Electrodomésticos", "MLA1574": "Hogar, Muebles y Jardín", "MLA407134": "Herramientas",
    "MLA1500": "Construcción", "MLA1276": "Deportes y Fitness", "MLA1246": "Belleza y Cuidado Personal",
    "MLA409431": "Salud y Equipamiento Médico", "MLA1144": "Consolas y Videojuegos", "MLA1132": "Juegos y Juguetes",
    "MLA1384": "Bebés", "MLA1071": "Animales y Mascotas", "MLA1430": "Ropa y Accesorios",
    "MLA1747": "Accesorios para Vehículos", "MLA1039": "Cámaras y Accesorios", "MLA1403": "Alimentos y Bebidas",
    "MLA1182": "Instrumentos Musicales", "MLA3025": "Libros, Revistas y Comics", "MLA1499": "Industrias y Oficinas",
}

def probe(token):
    """Diagnóstico: muestra qué recursos de la API responden con este token."""
    tests = ["/users/me", f"/sites/{SITE}/categories", "/categories/MLA1051",
             f"/highlights/{SITE}/category/MLA1051", f"/sites/{SITE}/search?q=celular&limit=1",
             f"/products/search?site_id={SITE}&q=celular&limit=1", f"/trends/{SITE}"]
    for t in tests:
        for tok in (token, None):
            try:
                r = http("GET", API + t, token=tok)
                print(f"PRUEBA OK   {'con' if tok else 'sin'} token  {t}  -> {str(r)[:90]}")
            except Exception as e:
                print(f"PRUEBA FALLA {'con' if tok else 'sin'} token  {t}  -> {str(e)[:110]}")

def chunks(lst, n):
    for i in range(0, len(lst), n): yield lst[i:i + n]

def affiliate(permalink, pid, links):
    if pid in links: return links[pid]
    if CFG.get("affiliate_mode") == "params" and permalink:
        base = permalink.split("#")[0].split("?")[0]
        return f"{base}?matt_word={CFG['matt_word']}&matt_tool={CFG['matt_tool']}"
    return permalink

def fetch(token):
    try:
        cats = http("GET", f"{API}/sites/{SITE}/categories", token=token)
    except RuntimeError as e:
        print("categorías bloqueadas, uso la lista fija:", str(e)[:120])
        cats = [{"id": k, "name": v} for k, v in CATS_FIJAS.items()]
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
    print(f"ranking: {len(found)} entradas ({sum(f['type']=='ITEM' for f in found)} ITEM, {sum(f['type']=='PRODUCT' for f in found)} PRODUCT)")
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
    root_cache = {}
    def root_name(cat_id, fallback):
        if not cat_id: return fallback
        if cat_id not in root_cache:
            try:
                c = http("GET", f"{API}/categories/{cat_id}", token=token)
                root_cache[cat_id] = (c.get("path_from_root") or [{}])[0].get("name") or fallback
            except RuntimeError:
                root_cache[cat_id] = fallback
        return root_cache[cat_id]
    seen = {}
    for f in sorted([f for f in found if f["type"] == "PRODUCT"], key=lambda f: f["pos"]):
        if f["id"] in seen: continue
        seen[f["id"]] = True
        try:
            p = http("GET", f"{API}/products/{f['id']}", token=token)
            res = http("GET", f"{API}/products/{f['id']}/items?limit=50", token=token).get("results", [])
        except RuntimeError as e:
            print("product:", str(e)[:120]); continue
        res = [x for x in res if x.get("price") and x.get("condition", "new") == "new"]
        if not res: continue
        # Precio que ve el comprador: la oferta más barata CON envío gratis (como el "Mejor precio" de Mercado Libre);
        # si ninguna tiene envío gratis, la más barata sumando el costo de envío.
        free = [x for x in res if (x.get("shipping") or {}).get("free_shipping")]
        cheapest = min(res, key=lambda x: x["price"])
        best = min(free, key=lambda x: x["price"]) if free else cheapest
        # Si hay una oferta sin envío gratis mucho más barata (típico en productos baratos, debajo del umbral
        # de envío gratis), esa es la que ve el comprador: mostramos esa y avisamos "+ envío".
        if cheapest["price"] < CFG.get("free_ship_threshold", 33000) and cheapest["price"] < best["price"] * 0.7:
            best = cheapest
        ship_free = bool((best.get("shipping") or {}).get("free_shipping"))
        lst = best.get("original_price")
        pics = p.get("pictures") or [{}]
        out.append({"id": f["id"], "name": p.get("name"), "price": best["price"], "list": lst if lst and lst > best["price"] else None,
                    "img": pics[0].get("url", ""), "permalink": p.get("permalink") or f"https://www.mercadolibre.com.ar/p/{f['id']}",
                    "cat": root_name(best.get("category_id") or p.get("category_id"), f["cat"]), "pos": f["pos"],
                    "free_ship": ship_free, "offers": len(res), "min_any": cheapest["price"]})
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
    print(f"productos leídos: {len(rows)}, con precio de lista: {sum(1 for r in rows if r['list'])}")
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
        if verdict == "new" and off < CFG["min_discount"] and r["pos"] > 2:
            continue
        products.append({"id": r["id"], "name": r["name"], "cat": r["cat"], "price": r["price"], "was": was, "off": off,
                         "img": r["img"], "link": affiliate(r["permalink"], r["id"], links), "pos": r["pos"], "free_ship": r.get("free_ship", True), "offers": r.get("offers"),
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
