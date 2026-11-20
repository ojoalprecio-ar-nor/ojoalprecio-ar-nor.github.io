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
TOPE = CFG.get("carrusel_tope", 40000)


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
    for linea in texto.split("\n"):
        for l in textwrap.wrap(linea, width=max(8, int(ancho / (f.size * 0.58)))) or [""]:
            w = d.textlength(l, font=f)
            d.text(((W - w) / 2, y), l, font=f, fill=color)
            y += int(f.size * 1.25)
    return y


def marca(d):
    f = font(30)
    t = "OJO AL PRECIO  ·  precios reales de Mercado Libre"
    d.text(((W - d.textlength(t, font=f)) / 2, H - 70), t, font=f, fill=CREMA)


def imagen_producto(url):
    try:
        r = requests.get(url, timeout=20); r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception:
        ph = Image.new("RGB", (800, 800), (235, 235, 235))
        ImageDraw.Draw(ph).text((300, 380), "sin foto", font=font(40), fill=(150, 150, 150))
        return ph


def sello(p, hist):
    h = list(hist.get(p["id"], {}).values())
    if p["verdict"] == "real": return "PRECIO MAS BAJO REGISTRADO", (30, 160, 80)
    if len(h) >= 3 and p["price"] > min(h) * 1.05: return f"OJO: ANTES ESTUVO A {fmt(min(h))}", (200, 60, 40)
    return "PRECIO ESTABLE: LO SEGUIMOS A DIARIO", (60, 90, 160)


def slide_producto(p, i, hist):
    img = fondo(); d = ImageDraw.Draw(img)
    d.text((60, 50), f"#{i}", font=font(64), fill=NARANJA)
    # tarjeta blanca con la foto
    card = Image.new("RGB", (900, 760), BLANCO)
    foto = imagen_producto(p["img"]); foto.thumbnail((820, 700))
    card.paste(foto, ((900 - foto.width) // 2, (760 - foto.height) // 2))
    mask = Image.new("L", card.size, 0); ImageDraw.Draw(mask).rounded_rectangle([0, 0, 900, 760], 40, fill=255)
    sombra = Image.new("RGBA", (940, 800), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle([20, 20, 920, 780], 40, fill=(0, 0, 0, 110))
    img.paste(sombra.filter(ImageFilter.GaussianBlur(12)), (70, 130), sombra.filter(ImageFilter.GaussianBlur(12)))
    img.paste(card, (90, 140), mask)
    d = ImageDraw.Draw(img)
    y = centrado(d, 930, corto(p["name"]), font(46), BLANCO)
    precio = fmt(p["price"])
    fp = font(92); d.text(((W - d.textlength(precio, font=fp)) / 2, y + 5), precio, font=fp, fill=NARANJA)
    txt, col = sello(p, hist); fs = font(34)
    tw = d.textlength(txt, font=fs); x0 = (W - tw) / 2 - 30
    d.rounded_rectangle([x0, y + 125, x0 + tw + 60, y + 185], 30, fill=col)
    d.text((x0 + 30, y + 135), txt, font=fs, fill=BLANCO)
    marca(d)
    return img


def portada(n, tope):
    img = fondo(); d = ImageDraw.Draw(img)
    y = centrado(d, 260, f"{n} joyitas de\nMercado Libre\npor menos de\n{fmt(tope)}", font(104), BLANCO)
    y = centrado(d, y + 50, "con el precio VERIFICADO:\nsin descuentos inflados", font(52), NARANJA)
    centrado(d, y + 60, "Deslizá →", font(48), CREMA)
    marca(d); return img


def cierre():
    img = fondo(); d = ImageDraw.Draw(img)
    y = centrado(d, 250, "¿Te sirvió?", font(110), BLANCO)
    y = centrado(d, y + 40, "Seguinos para no caer\nen descuentos truchos", font(64), NARANJA)
    y = centrado(d, y + 60, "Guardalo para después\nCompartilo con alguien\nque lo necesite", font(54), CREMA)
    centrado(d, y + 60, f"TikTok: @ojoalprecio.ar\nLinks y precios: {SITE}", font(40), BLANCO)
    marca(d); return img


def elegir(prods, hist, n=5):
    ok = [p for p in prods if p["cat"] in CATS_OK and p["price"] <= TOPE and p.get("img")]
    reales = sorted([p for p in ok if p["verdict"] == "real"], key=lambda p: -(p.get("off") or 0))
    resto = sorted([p for p in ok if p["verdict"] != "real"], key=lambda p: p.get("rank") or 99)
    usados = set(json.loads((OUT / "usados.json").read_text()) if (OUT / "usados.json").exists() else [])
    orden = [p for p in reales + resto if p["id"] not in usados] + [p for p in reales + resto if p["id"] in usados]
    return orden[:n]


def generar():
    prods = json.loads((ROOT / "docs" / "data.json").read_text(encoding="utf-8")).get("products", [])
    hist = json.loads((ROOT / "data" / "history.json").read_text(encoding="utf-8"))
    sel = elegir(prods, hist)
    if len(sel) < 3: sys.exit("No hay suficientes productos para el carrusel")
    tope = max(10000, ((max(p["price"] for p in sel) // 5000) + 1) * 5000)
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.jpg"): f.unlink()
    slides = [portada(len(sel), tope)] + [slide_producto(p, i + 1, hist) for i, p in enumerate(sel)] + [cierre()]
    rutas = []
    for i, s in enumerate(slides):
        r = OUT / f"{i:02d}.jpg"; s.save(r, quality=90); rutas.append(r)
    usados = (json.loads((OUT / "usados.json").read_text()) if (OUT / "usados.json").exists() else [])
    (OUT / "usados.json").write_text(json.dumps((usados + [p["id"] for p in sel])[-40:]))
    return sel, tope, rutas


def texto_fb(sel, tope):
    l = [f"💎 {len(sel)} joyitas de Mercado Libre por menos de {fmt(tope)}, con el precio verificado (sin descuentos inflados):", ""]
    for i, p in enumerate(sel, 1): l.append(f"{i}) {corto(p['name'], 8)}: {fmt(p['price'])}\n🛒 {p['link']}")
    l += ["", "📲 Ofertas reales todas las noches, gratis: t.me/ojoalprecionor", "🎵 Seguinos en TikTok: @ojoalprecio.ar"]
    return "\n".join(l)


def texto_tiktok(sel, tope):
    return (f"{len(sel)} joyitas de Mercado Libre por menos de {fmt(tope)} 💎 con el precio verificado ✅ "
            "Links en el perfil 🔗\n#mercadolibre #joyitas #ofertas #argentina #hogar #blackfriday #compras")


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
    sel, tope, rutas = generar()
    print("productos:", [corto(p["name"]) for p in sel])
    if "--solo-generar" in sys.argv: sys.exit(0)
    if "--sin-facebook" not in sys.argv: publicar_facebook(rutas, texto_fb(sel, tope))
    try: mandar_telegram(rutas, texto_tiktok(sel, tope))
    except Exception as e: print("telegram falló:", e)
