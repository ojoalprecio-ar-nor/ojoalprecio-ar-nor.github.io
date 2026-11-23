"""Carrusel "joyitas con precio real" (formato TikTok/Instagram, 1080x1350).

Arma 7 imágenes (portada, 5 productos, cierre) con los datos del día y:
  - las publica en la página de Facebook como una sola publicación de varias fotos;
  - se las manda al dueño por Telegram con el texto para TikTok (subida manual, 1 minuto).
La llama el Publicador continuo lunes, miércoles y viernes. Uso manual: python scripts/carrusel.py [--solo-generar] [--sin-facebook]
"""
import io, json, os, sys, textwrap, datetime as dt
from pathlib import Path
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
OUT = ROOT / "data" / "carrusel"
SITE = "ojoalprecio-ar-nor.github.io"
AR = dt.timezone(dt.timedelta(hours=-3))
W, H = 1080, 1350
VERDE, VERDE2, NARANJA, CREMA, BLANCO = (13, 58, 44), (24, 92, 68), (255, 122, 0), (255, 246, 230), (255, 255, 255)
CATS_OK = {"Hogar, Muebles y Jardín", "Electrodomésticos y Aires Ac.", "Electrónica, Audio y Video", "Herramientas",
           "Computación", "Belleza y Cuidado Personal", "Deportes y Fitness", "Celulares y Teléfonos",
           "Accesorios para Vehículos", "Cámaras y Accesorios", "Consolas y Videojuegos", "Juegos y Juguetes"}
CATS_OK |= {"Salud y Equipamiento Médico", "Joyas y Relojes", "Construcción", "Tendencias"}
TOPE = CFG.get("carrusel_tope", 40000)
# consumibles y cosas que no son "joyitas"
EXCLUIR = [w.lower() for w in CFG.get("carrusel_excluir", [
    "pila", "detergente", "tintura", "igora", "óleo", "oleo", "shampoo", "crema", "sérum", "serum", "protector solar",
    "creatina", "proteína", "proteina", "magnesio", "lubricante", "toallita", "pañal", "rollo", "papel", "yerba", "café",
    "galletita", "cerveza", "arena", "piedras sanitarias", "pintura", "membrana", "malla", "sahumerio", "libro", "resma",
    "suavizante", "jabón", "jabon", "desodorante", "aceite", "neumático", "neumatico", "cubierta", "llanta", "batería auto", "nafta",
    "látex", "latex", "enduido", "cemento", "impermeabilizante", "glucómetro", "glucometro", "glucosa", "tira reactiva",
    "jeringa", "preservativo", "tensiómetro", "pañales", "toalla femenina", "alimento", "balanceado"])]


def font(size, bold=True):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"]:
        if os.path.exists(p): return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def fmt(n): return "$ " + f"{round(n):,}".replace(",", ".")


def corto(nombre, n=6):
    pal = [w for w in nombre.replace(",", " ").split() if len(w) > 1][:n]
    return " ".join(pal)


def fondo():
    img = Image.new("RGB", (W, H), VERDE)
    d = ImageDraw.Draw(img)
    for y in range(H):  # degradé vertical
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(VERDE[i] * (1 - t) + VERDE2[i] * t) for i in range(3)))
    return img


def centrado(d, y, texto, f, color, ancho=W - 120):
    texto = "".join(ch for ch in texto if ord(ch) < 0x2190 or ch in "→").replace("  ", " ").strip()  # sin emojis (la tipografía no los tiene)
    for linea in texto.split("\n"):
        for l in textwrap.wrap(linea, width=max(8, int(ancho / (f.size * 0.58)))) or [""]:
            w = d.textlength(l, font=f)
            d.text(((W - w) / 2, y), l, font=f, fill=color)
            y += int(f.size * 1.25)
    return y


LINK_TT = SITE  # TikTok lleva a la portada: arriba de todo están los productos del último carrusel


def marca(d, link=None):
    f = font(30)
    t = "OJO AL PRECIO  ·  precios reales de Mercado Libre"
    d.text(((W - d.textlength(t, font=f)) / 2, H - 70), t, font=f, fill=CREMA)
    if link:
        fl = font(36)
        d.rounded_rectangle([60, H - 150, W - 60, H - 90], 30, fill=NARANJA)
        d.text(((W - d.textlength(link, font=fl)) / 2, H - 143), link, font=fl, fill=BLANCO)


def imagen_producto(url):
    try:
        r = requests.get(url, timeout=20); r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception:
        ph = Image.new("RGB", (800, 800), (235, 235, 235))
        ImageDraw.Draw(ph).text((300, 380), "sin foto", font=font(40), fill=(150, 150, 150))
        return ph


def sello(p, hist):
    if MODO == "subieron":
        pct, mn = pct_subio(p, hist)
        return f"SUBIO {pct}%  ·  ANTES {fmt(mn)}", (200, 60, 40)
    h = list(hist.get(p["id"], {}).values())
    if p["verdict"] == "real": return "PRECIO MAS BAJO REGISTRADO", (30, 160, 80)
    if len(h) >= 3 and p["price"] > min(h) * 1.05: return f"OJO: ANTES ESTUVO A {fmt(min(h))}", (200, 60, 40)
    return "PRECIO ESTABLE: LO SEGUIMOS A DIARIO", (60, 90, 160)


def slide_producto(p, i, hist):
    img = fondo(); d = ImageDraw.Draw(img)
    d.text((60, 50), f"#{i}", font=font(64), fill=NARANJA)
    # tarjeta blanca con la foto
    card = Image.new("RGB", (900, 650), BLANCO)
    foto = imagen_producto(p["img"]); foto.thumbnail((820, 600))
    card.paste(foto, ((900 - foto.width) // 2, (650 - foto.height) // 2))
    mask = Image.new("L", card.size, 0); ImageDraw.Draw(mask).rounded_rectangle([0, 0, 900, 650], 40, fill=255)
    sombra = Image.new("RGBA", (940, 690), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle([20, 20, 920, 670], 40, fill=(0, 0, 0, 110))
    img.paste(sombra.filter(ImageFilter.GaussianBlur(12)), (70, 115), sombra.filter(ImageFilter.GaussianBlur(12)))
    img.paste(card, (90, 125), mask)
    d = ImageDraw.Draw(img)
    y = centrado(d, 805, corto(p["name"]), font(46), BLANCO)
    precio = fmt(p["price"])
    fp = font(92); d.text(((W - d.textlength(precio, font=fp)) / 2, y + 5), precio, font=fp, fill=NARANJA)
    txt, col = sello(p, hist); fs = font(34)
    tw = d.textlength(txt, font=fs); x0 = (W - tw) / 2 - 30
    d.rounded_rectangle([x0, y + 125, x0 + tw + 60, y + 185], 30, fill=col)
    d.text((x0 + 30, y + 135), txt, font=fs, fill=BLANCO)
    marca(d, f"LINK #{i}: {LINK_TT}")
    return img


GANCHO = {}
MODO = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--modo=")), "normal")
BF = dt.date(2026, 11, 27)


def pct_subio(p, hist):
    h = list(hist.get(p["id"], {}).values())
    if len(h) >= 3 and min(h) * 1.05 < p["price"] <= min(h) * 1.6:  # más de 60% suele ser cambio de modelo, no suba real
        return round((p["price"] / min(h) - 1) * 100), min(h)
    return 0, None


def elegir_gancho(n, tope):
    man_p = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--portada=")), None)
    man_t = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--titulo=")), None)
    if man_p and man_t:
        GANCHO["portada"], GANCHO["titulo"] = man_p.replace("|", "\n"), man_t
        GANCHO["sub"] = "con el precio VERIFICADO:\nsin descuentos inflados"
        return
    _elegir_gancho_auto(n, tope)


def _elegir_gancho_auto(n, tope):
    """Rota la portada para que cada carrusel tenga otro gancho (y uno especial la semana del Black Friday)."""
    t = fmt(tope)
    opciones = [
        (f"{n} joyitas de\nMercado Libre\npor menos de\n{t}", f"{n} joyitas de Mercado Libre por menos de {t} 💎"),
        ("Cosas de\nMercado Libre\nque no sabías\nque necesitabas", "Cosas de Mercado Libre que no sabías que necesitabas 👀"),
        (f"{n} cosas para\ntu casa por\nmenos de\n{t}", f"{n} cosas para tu casa por menos de {t} 🏠"),
        ("Lo más vendido\nde Mercado Libre\nesta semana", "Lo más vendido de Mercado Libre esta semana 🔥"),
        (f"Ideas para\nregalar por\nmenos de\n{t}", f"Ideas para regalar por menos de {t} 🎁"),
    ]
    hoy = dt.datetime.now(AR).date()
    faltan = (BF - hoy).days
    GANCHO["sub"] = (f"Faltan {faltan} días para el Black Friday:\nprecios VERIFICADOS" if 0 < faltan <= 7 else
                     "con el precio VERIFICADO:\nsin descuentos inflados")
    if MODO == "subieron":
        GANCHO["portada"] = "OJO: estos\nproductos\nSUBIERON antes\ndel Black Friday"
        GANCHO["titulo"] = "⚠️ Estos productos SUBIERON de precio antes del Black Friday 👀"
        GANCHO["sub"] = (f"Faltan {faltan} días: que no te\nvendan un aumento como oferta" if faltan > 0 else "Que no te vendan un aumento como oferta")
        return
    if dt.date(2026, 11, 21) <= hoy <= dt.date(2026, 11, 30):
        opciones.append(("¿Ofertas reales\nde Black Friday?\nEstas SÍ", "¿Ofertas reales de Black Friday? Estas SÍ ✅"))
    hfile = OUT / "historial.json"
    k = len(json.loads(hfile.read_text())) if hfile.exists() else 0
    GANCHO["portada"], GANCHO["titulo"] = opciones[k % len(opciones)] if not (len(opciones) > 5 and k % 2) else opciones[-1]


def portada(n, tope):
    img = fondo(); d = ImageDraw.Draw(img)
    y = centrado(d, 200 if MODO == "subieron" else 260, GANCHO["portada"], font(96 if MODO == "subieron" else 104), BLANCO)
    y = centrado(d, y + 50, GANCHO.get("sub", "con el precio VERIFICADO:\nsin descuentos inflados"), font(52), NARANJA)
    centrado(d, y + 60, "Deslizá →", font(48), CREMA)
    marca(d, f"LINKS: {LINK_TT}"); return img


def cierre():
    img = fondo(); d = ImageDraw.Draw(img)
    y = centrado(d, 250, "¿Te sirvió?", font(110), BLANCO)
    y = centrado(d, y + 40, "Seguinos para no caer\nen descuentos truchos", font(64), NARANJA)
    y = centrado(d, y + 60, "Guardalo para después\nCompartilo con alguien\nque lo necesite", font(54), CREMA)
    centrado(d, y + 60, "TikTok: @ojoalprecio.ar", font(40), BLANCO)
    marca(d, f"LINKS: {LINK_TT}"); return img



STOP = {"de", "con", "para", "y", "el", "la", "los", "las", "en", "por", "x", "c/u", "c/", "sin", "un", "una", "color", "kit", "set", "pack"}


def palabras(nombre):
    return {w for w in "".join(ch if ch.isalnum() else " " for ch in nombre.lower()).split() if len(w) > 2 and w not in STOP}


def parecido(a, b):
    A, B = palabras(a), palabras(b)
    return len(A & B) / max(1, min(len(A), len(B), 6))


def recientes():
    """Nombres de los productos de los últimos carruseles (para no repetir ni casi-repetir)."""
    hfile = OUT / "historial.json"
    h = json.loads(hfile.read_text()) if hfile.exists() else []
    return [x["name"] for c in h[:8] for x in c["items"]]


def sin_parecidos(cands, n):
    usados_n = recientes(); sel = []
    for p in cands:
        if any(parecido(p["name"], u) >= 0.5 for u in usados_n): continue
        if any(parecido(p["name"], q["name"]) >= 0.5 for q in sel): continue
        sel.append(p)
        if len(sel) == n: break
    return sel



def _norm(t):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


def terminos_tendencia():
    """Búsquedas en tendencia de Mercado Libre (data/tendencias_busquedas.csv) + palabras del tema del momento (config 'tema')."""
    import csv
    t = []
    f = ROOT / "data" / "tendencias_busquedas.csv"
    if f.exists():
        for r in csv.DictReader(open(f, encoding="utf-8-sig"), delimiter=";"):
            w = _norm(r.get("termino", "")).strip()
            if w and w not in ("ofertas", "buscar", "navidad") and not w.startswith("mecado"): t.append(w)
    return t[:60] + [_norm(x) for x in CFG.get("tema", [])]


def puntaje_tendencia(p, terms):
    nombre = _norm(p["name"]); ws = set("".join(ch if ch.isalnum() else " " for ch in nombre).split())
    pts = 0
    for i, term in enumerate(terms):
        tw = [w for w in term.split() if len(w) > 2 or w.isdigit()]
        if tw and all(w in ws or w in nombre for w in tw): pts = max(pts, 100 - min(i, 60))
    return pts

def elegir(prods, hist, n=5):
    ok = [p for p in prods if p["cat"] in CATS_OK and p["price"] <= TOPE and p.get("img")
          and not any(w in p["name"].lower() for w in EXCLUIR)]
    terms = terminos_tendencia()
    # primero lo que coincide con búsquedas en tendencia / tema del momento, después descuentos reales, después ranking
    reales = sorted([p for p in ok if p["verdict"] == "real"], key=lambda p: (-puntaje_tendencia(p, terms), -(p.get("off") or 0)))
    resto = sorted([p for p in ok if p["verdict"] != "real"], key=lambda p: (-puntaje_tendencia(p, terms), p.get("rank") or 99))
    tend = [p for p in reales + resto if puntaje_tendencia(p, terms) > 0]
    reales = [p for p in reales if p not in tend]; resto = [p for p in resto if p not in tend]
    reales = tend + reales
    usados = set(json.loads((OUT / "usados.json").read_text()) if (OUT / "usados.json").exists() else [])
    orden = [p for p in reales + resto if p["id"] not in usados]
    sel = sin_parecidos(orden, n)
    return sel if len(sel) >= n else (sel + [p for p in reales + resto if p not in sel])[:n]


def elegir_subieron(prods, hist, n=5):
    ok = [p for p in prods if p["cat"] in CATS_OK and p.get("img") and p["price"] <= 150000
          and not any(w in p["name"].lower() for w in EXCLUIR) and pct_subio(p, hist)[0] > 0]
    ok.sort(key=lambda p: -pct_subio(p, hist)[0])
    usados = set(json.loads((OUT / "usados.json").read_text()) if (OUT / "usados.json").exists() else [])
    sel = sin_parecidos([p for p in ok if p["id"] not in usados], n)
    return sel if len(sel) >= 3 else ([p for p in ok if p["id"] not in usados] + [p for p in ok if p["id"] in usados])[:n]


def generar(ids=None):
    prods = json.loads((ROOT / "docs" / "data.json").read_text(encoding="utf-8")).get("products", [])
    hist = json.loads((ROOT / "data" / "history.json").read_text(encoding="utf-8"))
    if ids:
        por_id = {p["id"]: p for p in prods}
        sel = [por_id[i] for i in ids if i in por_id]
    elif MODO == "subieron":
        sel = elegir_subieron(prods, hist)
    else:
        sel = elegir(prods, hist)
    if len(sel) < 3: sys.exit("No hay suficientes productos para el carrusel")
    tope = max(10000, ((max(p["price"] for p in sel) // 5000) + 1) * 5000)
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.jpg"): f.unlink()
    elegir_gancho(len(sel), tope)
    slides = [portada(len(sel), tope)] + [slide_producto(p, i + 1, hist) for i, p in enumerate(sel)] + [cierre()]
    rutas = []
    for i, s in enumerate(slides):
        r = OUT / f"{i:02d}.jpg"; s.save(r, quality=90); rutas.append(r)
    usados = (json.loads((OUT / "usados.json").read_text()) if (OUT / "usados.json").exists() else [])
    (OUT / "usados.json").write_text(json.dumps((usados + [p["id"] for p in sel])[-80:]))
    pagina_tt(sel, tope)
    return sel, tope, rutas


def pagina_tt(sel, tope):
    """Página corta /tt/ con los links de los últimos carruseles (el más nuevo arriba), numerados igual que las fotos."""
    import html
    hfile = OUT / "historial.json"
    histo = json.loads(hfile.read_text()) if hfile.exists() else []
    histo.insert(0, {"fecha": dt.datetime.now(AR).strftime("%d/%m %H:%M"), "tope": tope,
                     "items": [{"name": corto(p["name"], 9), "price": p["price"], "img": p["img"], "link": p["link"]} for p in sel]})
    histo = histo[:10]
    hfile.parent.mkdir(parents=True, exist_ok=True); hfile.write_text(json.dumps(histo, ensure_ascii=False))
    secciones = ""
    for k, c in enumerate(histo):
        items = "".join(
            f'<a class="it" href="{html.escape(x["link"])}" rel="noopener sponsored"><span class="n">#{i}</span>'
            f'<img src="{html.escape(x["img"])}" alt="" loading="lazy"><span class="t">{html.escape(x["name"])}'
            f'<b>{fmt(x["price"])}</b><em>Ver en Mercado Libre →</em></span></a>' for i, x in enumerate(c["items"], 1))
        titulo = "Último carrusel" if k == 0 else "Carrusel anterior"
        secciones += f'<h2>{titulo} · {c["fecha"]}</h2><p>Joyitas por menos de {fmt(c["tope"])}</p>{items}'
    doc = f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Links de los carruseles | Ojo al Precio</title><meta name="description" content="Links de las joyitas de Mercado Libre de los carruseles de Ojo al Precio.">
<style>body{{margin:0;font-family:system-ui,sans-serif;background:#0d3a2c;color:#fff}}main{{max-width:560px;margin:auto;padding:16px}}
h1{{font-size:24px;margin:8px 0}}h2{{font-size:19px;margin:26px 0 2px;color:#ff9a3c}}p{{color:#ffe;opacity:.85;margin:4px 0 10px}}
.it{{display:flex;gap:12px;align-items:center;background:#fff;color:#111;border-radius:14px;padding:10px;margin:10px 0;text-decoration:none}}
.it img{{width:84px;height:84px;object-fit:contain}}.n{{font-weight:800;color:#ff7a00;font-size:22px;min-width:34px}}
.t{{display:flex;flex-direction:column;gap:3px;font-size:15px}}.t b{{font-size:20px}}.t em{{color:#1a7f4b;font-style:normal;font-weight:600}}
.f{{display:block;text-align:center;color:#fff;margin:18px 0}}</style></head><body><main>
<h1>💎 Links de los carruseles</h1><p>Buscá el carrusel que viste y tocá el mismo número de la foto.</p>{secciones}
<a class="f" href="../">🔎 Ver todas las ofertas con historial de precios</a><a class="f" href="https://t.me/ojoalprecionor">✈️ Ofertas gratis en Telegram</a>
</main></body></html>"""
    d = ROOT / "docs" / "tt"; d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(doc, encoding="utf-8")
    bloque_home(histo[0])


def bloque_home(c):
    """Sección 'Vistos en TikTok' arriba de todo en la portada, con los productos del último carrusel."""
    import html, re
    cards = "".join(
        f'<a href="{html.escape(x["link"])}" rel="noopener sponsored" style="flex:0 0 150px;scroll-snap-align:start;background:#fff;color:#111;'
        f'border-radius:14px;padding:8px;text-decoration:none;display:flex;flex-direction:column;gap:4px">'
        f'<span style="font-weight:800;color:#ff7a00">#{i}</span><img src="{html.escape(x["img"])}" alt="" loading="lazy" '
        f'style="width:100%;height:110px;object-fit:contain"><span style="font-size:13px;line-height:1.2">{html.escape(x["name"])}</span>'
        f'<b style="font-size:16px">{fmt(x["price"])}</b><span style="font-size:12px;color:#1a7f4b;font-weight:700">Ver en Mercado Libre →</span></a>'
        for i, x in enumerate(c["items"], 1))
    sec = (f'<!--tiktok--><section style="max-width:100%;box-sizing:border-box;overflow:hidden;margin:18px 0;padding:14px;border-radius:16px;background:#0d3a2c;color:#fff">'
           f'<h2 style="font-size:18px;margin:0 0 4px">💎 Vistos en TikTok</h2><p style="margin:0 0 10px;opacity:.85;font-size:14px">'
           f'Los productos del último carrusel ({c["fecha"]}). Tocá el número que viste. <a href="tt/" style="color:#ff9a3c">Carruseles anteriores</a></p>'
           f'<div style="display:flex;gap:10px;overflow-x:auto;scroll-snap-type:x mandatory;padding-bottom:6px">{cards}</div></section><!--/tiktok-->')
    idx = ROOT / "docs" / "index.html"
    s = idx.read_text(encoding="utf-8")
    if "<!--tiktok-->" in s:
        s = re.sub(r"<!--tiktok-->.*?<!--/tiktok-->", lambda m: sec, s, flags=re.S)
        idx.write_text(s, encoding="utf-8")


def texto_fb(sel, tope):
    l = [f"{GANCHO['titulo']}\nCon el precio verificado (sin descuentos inflados):", ""]
    for i, p in enumerate(sel, 1): l.append(f"{i}) {corto(p['name'], 8)}: {fmt(p['price'])}\n🛒 {p['link']}")
    l += ["", "📲 Ofertas reales todas las noches, gratis: t.me/ojoalprecionor", "🎵 Seguinos en TikTok: @ojoalprecio.ar"]
    return "\n".join(l)


def texto_tiktok(sel, tope):
    return (f"{GANCHO['titulo']} Con el precio verificado ✅ "
            f"🔗 Links en {LINK_TT} (arriba de todo están los de este video)\n#mercadolibre #joyitas #ofertas #argentina #hogar #blackfriday #blackfridayargentina #compras")


def page_token(token, page):
    try:
        r = requests.get(f"https://graph.facebook.com/v21.0/{page}", params={"fields": "access_token", "access_token": token}, timeout=30)
        return r.json().get("access_token") or token
    except Exception: return token


def publicar_facebook(rutas, mensaje):
    token = os.environ.get("FB_PAGE_TOKEN", "").strip(); page = str(CFG.get("fb_page_id", ""))
    if not token or not page or not CFG.get("facebook_enabled", True): print("Facebook no configurado o pausado"); return
    tk = page_token(token, page); ids = []
    for r in rutas:
        with open(r, "rb") as fh:
            j = requests.post(f"https://graph.facebook.com/v21.0/{page}/photos", data={"published": "false", "access_token": tk},
                              files={"source": fh}, timeout=60).json()
        if "id" not in j: sys.exit(f"Facebook (foto) respondió error: {j}")
        ids.append(j["id"])
    data = {"message": mensaje, "access_token": tk}
    for i, x in enumerate(ids): data[f"attached_media[{i}]"] = json.dumps({"media_fbid": x})
    j = requests.post(f"https://graph.facebook.com/v21.0/{page}/feed", data=data, timeout=60).json()
    print("carrusel en Facebook:", j.get("id") or j)


def mandar_telegram(rutas, texto):
    sys.path.insert(0, str(Path(__file__).parent))
    import aviso
    chat = aviso.admin_chat()
    if not chat: print("Sin chat del dueño; no se manda a Telegram"); return
    tok = aviso.TOKEN
    aviso.enviar("🎬 Carrusel listo para TikTok (opcional, 1 minuto): guardá las fotos de abajo, en TikTok tocá + → Fotos, "
                 "elegilas en orden y pegá este texto:\n\n" + texto)
    files = {f"f{i}": open(r, "rb") for i, r in enumerate(rutas)}
    media = [{"type": "photo", "media": f"attach://f{i}"} for i in range(len(rutas))]
    j = requests.post(f"https://api.telegram.org/bot{tok}/sendMediaGroup", data={"chat_id": chat, "media": json.dumps(media)},
                      files=files, timeout=120).json()
    print("telegram:", j.get("ok"))


if __name__ == "__main__":
    ids = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--ids=")), None)
    sel, tope, rutas = generar(ids)
    print("productos:", [corto(p["name"]) for p in sel])
    if "--solo-generar" in sys.argv: sys.exit(0)
    if "--sin-facebook" not in sys.argv: publicar_facebook(rutas, texto_fb(sel, tope))
    try: mandar_telegram(rutas, texto_tiktok(sel, tope))
    except Exception as e: print("telegram falló:", e)
