"""Publica una oferta en la página de Facebook de Ojo al Precio (Graph API).
Usa la misma selección que Telegram, con su propio registro (data/posted_fb.json).
Secretos: FB_PAGE_TOKEN. Config: fb_page_id (config.json)."""
import json, os, sys, datetime as dt, urllib.request, urllib.parse, urllib.error
from pathlib import Path
from telegram import pick, fmt, ROOT, CFG, SITE, in_schedule

POSTED = ROOT / "data" / "posted_fb.json"
TG = "t.me/" + CFG.get("telegram_chat", "@ojoalprecionor").lstrip("@")

def text(p):
    lines = [p["name"], ""]
    price = f"💰 {fmt(p['price'])}"
    if p.get("was"): price += f" (antes {fmt(p['was'])}) 🔻{p['off']}% OFF"
    lines.append(price)
    lines.append("🚚 Envío gratis" if p.get("free_ship", True) else "🚚 + costo de envío")
    if p["verdict"] == "real": lines.append(f"✅ Descuento real: {p['note']}")
    lines += ["", f"🛒 Compralo acá 👉 {p['link']}", "", f"📲 Más ofertas todas las noches: {TG}", f"🔎 Lista completa: {SITE}"]
    return "\n".join(lines)

def main():
    token = os.environ.get("FB_PAGE_TOKEN", "").strip()
    page = str(CFG.get("fb_page_id", "")).strip()
    if not token or not page:
        sys.exit("Falta FB_PAGE_TOKEN (secreto) o fb_page_id (config.json)")
    if not in_schedule():
        print("Fuera del horario de publicación"); return
    products = json.loads((ROOT / "docs" / "data.json").read_text(encoding="utf-8")).get("products", [])
    posted = json.loads(POSTED.read_text(encoding="utf-8")) if POSTED.exists() else {}
    p = pick(products, posted)
    if not p:
        print("No hay ofertas nuevas"); return
    if "--dry" in sys.argv:
        print(text(p)); return
    data = urllib.parse.urlencode({"url": p["img"], "caption": text(p), "access_token": token}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(f"https://graph.facebook.com/v21.0/{page}/photos", data=data), timeout=60) as r:
            res = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        sys.exit("Facebook respondió error: " + e.read().decode(errors="ignore")[:300])
    print("publicado en Facebook:", res.get("post_id") or res.get("id"), p["name"][:60])
    posted[p["id"]] = dt.date.today().isoformat()
    POSTED.write_text(json.dumps(posted, ensure_ascii=False, indent=1), encoding="utf-8")

if __name__ == "__main__":
    main()
