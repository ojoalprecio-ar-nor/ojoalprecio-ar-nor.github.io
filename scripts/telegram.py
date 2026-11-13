"""Publica una oferta de Ojo al Precio en el canal de Telegram.
Elige la mejor oferta de docs/data.json que no se haya publicado en los últimos 7 días
y la envía con foto, precio y botón al producto. Guarda lo publicado en data/posted.json.
Secretos: TELEGRAM_BOT_TOKEN. Config: telegram_chat (en config.json, ej. "@ojoalprecio")."""
import json, os, sys, datetime as dt, urllib.request, urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
POSTED = ROOT / "data" / "posted.json"
SITE = "https://ojoalprecio-ar-nor.github.io"

def fmt(n): return "$ " + f"{round(n):,}".replace(",", ".")

def esc(t): return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def in_schedule():
    """Durante la promo (hasta CFG promo_until) publica de 12 a 23 h; después, solo de 19 a 23 h (hora argentina)."""
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=-3)))
    promo = now.date().isoformat() <= CFG.get("promo_until", "")
    start = 12 if promo else 19
    return start <= now.hour <= 23 or "--force" in sys.argv

def pick(products, posted):
    cutoff = (dt.date.today() - dt.timedelta(days=CFG.get("repeat_days", 3))).isoformat()
    recent = {k for k, v in posted.items() if v >= cutoff}
    cand = [p for p in products if p["id"] not in recent and p.get("img")]
    order = {"real": 0, "new": 1, "fake": 3}
    # Primero descuentos reales, después los de mayor % OFF; nunca los marcados "Ojo"
    cand = [p for p in cand if p["verdict"] != "fake"]
    cand.sort(key=lambda p: (order.get(p["verdict"], 2), -(p.get("off") or 0), p["rank"]))
    return cand[0] if cand else None

def caption(p):
    lines = [f"<b>{esc(p['name'])}</b>", ""]
    price = f"💰 <b>{fmt(p['price'])}</b>"
    if p.get("was"): price += f"  <s>{fmt(p['was'])}</s>  🔻{p['off']}% OFF"
    lines.append(price)
    lines.append("🚚 Envío gratis" if p.get("free_ship", True) else "🚚 + costo de envío")
    if p["verdict"] == "real": lines.append(f"✅ Descuento real: {esc(p['note'])}")
    else: lines.append("📊 Lo estamos siguiendo para confirmar si el descuento es real")
    lines += ["", f"🏷 {esc(p['cat'])} · #{p['rank']} en tendencia", "", f"⚠️ ¿Cuáles subieron de precio antes del Black Friday? {SITE}/black-friday/?ref=tg"]
    return "\n".join(lines)

def send(token, chat, p):
    data = {"chat_id": chat, "photo": p["img"], "caption": caption(p), "parse_mode": "HTML",
            "reply_markup": json.dumps({"inline_keyboard": [[{"text": "🛒 Ver en Mercado Libre", "url": p["link"]}]]})}
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendPhoto", data=urllib.parse.urlencode(data).encode())
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = CFG.get("telegram_chat", "").strip()
    if not token or not chat:
        sys.exit("Falta TELEGRAM_BOT_TOKEN (secreto) o telegram_chat (config.json)")
    if not in_schedule():
        print("Fuera del horario de publicación"); return
    products = json.loads((ROOT / "docs" / "data.json").read_text(encoding="utf-8")).get("products", [])
    posted = json.loads(POSTED.read_text(encoding="utf-8")) if POSTED.exists() else {}
    p = pick(products, posted)
    if not p:
        print("No hay ofertas nuevas para publicar"); return
    if "--dry" in sys.argv:
        print(caption(p)); return
    res = send(token, chat, p)
    print("publicado:", res.get("ok"), p["name"][:60])
    posted[p["id"]] = dt.date.today().isoformat()
    POSTED.write_text(json.dumps(posted, ensure_ascii=False, indent=1), encoding="utf-8")

if __name__ == "__main__":
    main()
