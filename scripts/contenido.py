"""Publica en la página de Facebook UNA publicación propia por día (no oferta), armada con los datos del día.
La llama el Publicador continuo a las 11:15 (hora argentina). Del 15 al 21/11/2026 ya hay publicaciones programadas.
Uso: python scripts/contenido.py [--force]"""
import json, os, sys, datetime as dt, urllib.request, urllib.parse, urllib.error
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
SITE = "https://ojoalprecio-ar-nor.github.io"
TG = "t.me/ojoalprecionor"
AR = dt.timezone(dt.timedelta(hours=-3))
BF = dt.date(2026, 11, 27)
YA_PROGRAMADO = (dt.date(2026, 11, 15), dt.date(2026, 11, 21))
LOG = ROOT / "data" / "contenido_fb.json"

def page_token(token, page):
    try:
        u = f"https://graph.facebook.com/v21.0/{page}?fields=access_token&access_token={urllib.parse.quote(token)}"
        with urllib.request.urlopen(u, timeout=30) as r:
            return json.loads(r.read().decode()).get("access_token") or token
    except Exception:
        return token

def datos():
    prods = json.loads((ROOT / "docs" / "data.json").read_text(encoding="utf-8")).get("products", [])
    hist = json.loads((ROOT / "data" / "history.json").read_text(encoding="utf-8"))
    subieron = 0
    for p in prods:
        h = list(hist.get(p["id"], {}).values())
        if len(h) >= 3 and p["price"] > min(h) * 1.05: subieron += 1
    reales = [p for p in prods if p["verdict"] == "real"]
    return len(prods), subieron, len(reales)

def fmt_n(n): return f"{n:,}".replace(",", ".")

def texto(hoy):
    total, subieron, reales = datos()
    faltan = (BF - hoy).days
    if 0 < faltan <= 12:
        if faltan == 1:
            return (f"⏰ ¡Mañana es Black Friday!\n\nAntes de comprar, fijate el historial de precio: de {total} productos que seguimos, "
                    f"{subieron} hoy están más caros que su mínimo registrado. Que no te vendan un aumento como descuento.", f"{SITE}/black-friday/?ref=fbauto")
        return (f"⏳ Faltan {faltan} días para el Black Friday (viernes 27/11).\n\nDe {total} productos más vendidos que seguimos todos los días, "
                f"{subieron} ya están más caros que su precio más bajo registrado. Mirá cuáles 👇", f"{SITE}/black-friday/?ref=fbauto")
    if faltan == 0:
        return ("🛍️ ¡Hoy es Black Friday!\n\nRegla de oro: si el precio de hoy no es más bajo que el mínimo de las últimas semanas, no es oferta. "
                "Lo controlamos por vos en la web 👇", f"{SITE}/?ref=fbauto")
    banco = [
        ("🕵️ 3 señales de un descuento trucho:\n\n1️⃣ El precio \"antes\" nunca existió o duró un día.\n2️⃣ Lo subieron semanas antes de la promo.\n3️⃣ El descuento se lo come el envío o las cuotas con interés.", None),
        (f"✅ Hoy encontramos {reales} productos con descuento real (más baratos que su precio habitual).\n\nLos publicamos gratis todas las noches en Telegram: {TG}", None),
        ("👀 ¿Qué producto querés comprar y estás esperando que baje?\n\nDejalo en los comentarios y lo sumamos al seguimiento de precios.", None),
        ("📉 Cómo usar Ojo al Precio en 10 segundos:\n\n🔎 Buscá el producto.\n📈 Mirá el gráfico del precio.\n✅ Si está en su mínimo, es buen momento. Si subió, esperá.", f"{SITE}/?ref=fbauto"),
        ("💳 ¿Contado o cuotas sin interés?\n\nSi el precio en cuotas es más alto que el de contado, no son \"sin interés\": el interés está escondido. Comparalos siempre.", None),
        (f"📊 Seguimos todos los días el precio de {total} productos de los más vendidos de Mercado Libre.\n\nSi querés ver el historial de cualquiera antes de comprar, está todo acá 👇", f"{SITE}/?ref=fbauto"),
        ("🧾 Tip: antes de comprar, mirá la reputación del vendedor y si el envío es gratis. Un 10% de descuento con envío caro puede salir más caro.", None),
    ]
    return banco[hoy.toordinal() % len(banco)]

def main():
    force = "--force" in sys.argv
    if not CFG.get("facebook_enabled", True): print("Facebook pausado"); return
    token = os.environ.get("FB_PAGE_TOKEN", "").strip(); page = str(CFG.get("fb_page_id", ""))
    if not token or not page: sys.exit("Falta FB_PAGE_TOKEN o fb_page_id")
    hoy = dt.datetime.now(AR).date()
    if YA_PROGRAMADO[0] <= hoy <= YA_PROGRAMADO[1] and not force: print("Hoy ya hay publicación programada"); return
    log = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {}
    if log.get("ultima") == hoy.isoformat() and not force: print("Ya se publicó el contenido de hoy"); return
    msg, link = texto(hoy)
    data = {"message": msg, "access_token": page_token(token, page)}
    if link: data["link"] = link
    req = urllib.request.Request(f"https://graph.facebook.com/v21.0/{page}/feed", data=urllib.parse.urlencode(data).encode())
    try:
        with urllib.request.urlopen(req, timeout=30) as r: print("contenido publicado:", json.loads(r.read().decode()).get("id"))
    except urllib.error.HTTPError as e:
        sys.exit("Facebook respondió error: " + e.read().decode(errors="ignore")[:300])
    LOG.write_text(json.dumps({"ultima": hoy.isoformat()}), encoding="utf-8")

if __name__ == "__main__": main()
