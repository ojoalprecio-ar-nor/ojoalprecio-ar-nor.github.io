"""Deja programadas en Facebook publicaciones propias (no ofertas), una por día a las 11:15 (hora argentina).
Se ven y se editan en Meta Business Suite → Planificador. Uso: python scripts/programar.py"""
import json, os, sys, datetime as dt, urllib.request, urllib.parse, urllib.error
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
SITE = "https://ojoalprecio-ar-nor.github.io"
AR = dt.timezone(dt.timedelta(hours=-3))
POSTS = [
    ("2026-11-15", "⏳ Faltan 12 días para el Black Friday (viernes 27/11).\n\nAntes de que aparezcan los carteles de \"70% OFF\", ya estamos viendo productos que SUBIERON de precio estos días. Mirá cuáles son 👇", f"{SITE}/black-friday/?ref=fbprog"),
    ("2026-11-16", "🕵️ 3 señales de un descuento trucho:\n\n1️⃣ El precio \"antes\" nunca existió o duró un día.\n2️⃣ Lo subieron una o dos semanas antes de la promo.\n3️⃣ El descuento se come con el envío o con cuotas con interés.\n\nNosotros anotamos el precio de los más vendidos de Mercado Libre todos los días para que no te pase.", None),
    ("2026-11-17", "👀 ¿Qué estás esperando para comprar en el Black Friday?\n\nDejalo en los comentarios y lo sumamos al seguimiento de precios: si de verdad baja, lo publicamos.", None),
    ("2026-11-18", "📈 Muchos de los productos más vendidos ya están más caros que hace dos semanas.\n\nSi el 27 te los muestran \"en oferta\", fijate primero en el historial de precio. Acá podés ver cuáles subieron:", f"{SITE}/black-friday/?ref=fbprog"),
    ("2026-11-19", "📲 ¿No querés perderte las ofertas que sí son reales?\n\nTe las mandamos gratis todas las noches por Telegram, sin spam y con el historial de precio: t.me/ojoalprecionor", None),
    ("2026-11-20", "🗓️ Falta una semana para el Black Friday.\n\nCómo usar Ojo al Precio en 10 segundos:\n🔎 Buscá el producto.\n📉 Mirá el gráfico del precio.\n✅ Si está en su mínimo, es buen momento. Si subió, esperá.", f"{SITE}/?ref=fbprog"),
    ("2026-11-21", "💳 ¿Descuento o cuotas sin interés?\n\nRegla rápida: con inflación, las cuotas sin interés de verdad suelen convenir. Pero si el precio en cuotas es más alto que el de contado, no son \"sin interés\": son con interés escondido. Comparalos siempre.", None),
]

def page_token(token, page):
    """Si el secreto es un token de usuario del sistema, obtiene el token de la página; si no, usa el mismo."""
    try:
        u = f"https://graph.facebook.com/v21.0/{page}?fields=access_token&access_token={urllib.parse.quote(token)}"
        with urllib.request.urlopen(u, timeout=30) as r:
            return json.loads(r.read().decode()).get("access_token") or token
    except Exception:
        return token

def main():
    token = os.environ.get("FB_PAGE_TOKEN", "").strip(); page = str(CFG["fb_page_id"])
    if not token: sys.exit("Falta FB_PAGE_TOKEN")
    token = page_token(token, page)
    ahora = dt.datetime.now(dt.timezone.utc)
    for fecha, msg, link in POSTS:
        cuando = dt.datetime.fromisoformat(fecha + "T11:15:00").replace(tzinfo=AR)
        if cuando < ahora + dt.timedelta(minutes=15): print("salteo (ya pasó)", fecha); continue
        data = {"message": msg, "published": "false", "scheduled_publish_time": str(int(cuando.timestamp())), "access_token": token}
        if link: data["link"] = link
        req = urllib.request.Request(f"https://graph.facebook.com/v21.0/{page}/feed", data=urllib.parse.urlencode(data).encode())
        try:
            with urllib.request.urlopen(req, timeout=30) as r: print("programado", fecha, json.loads(r.read().decode()).get("id"))
        except urllib.error.HTTPError as e:
            print("error", fecha, e.read().decode(errors="ignore")[:200])
if __name__ == "__main__": main()
