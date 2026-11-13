"""Avisos privados de Ojo al Precio al dueño por Telegram (sin depender de Claude).

Uso (lo llama el Publicador continuo):
  python scripts/aviso.py registrar   -> si el dueño abrió el bot con el enlace de alta, guarda su chat (cifrado)
  python scripts/aviso.py grupos      -> manda los 2 grupos de Facebook del día + texto listo para copiar
  python scripts/aviso.py salud       -> revisa que todo funcione; avisa solo si hay un problema (lunes: resumen)
  python scripts/aviso.py whoami      -> muestra el usuario del bot (para armar el enlace de alta)
Secretos: TELEGRAM_BOT_TOKEN, GH_TOKEN (opcional, para revisar las corridas)."""
import base64, datetime as dt, hashlib, json, os, sys, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
ADMIN = ROOT / "data" / "admin.enc"
AR = dt.timezone(dt.timedelta(hours=-3))
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

GRUPOS = [
    ("Todo Salta Ofertas Compra Venta", "https://www.facebook.com/groups/ventassaltall/"),
    ("Ofertas Mercado libre", "https://www.facebook.com/groups/2900962570065188/"),
    ("Compra Venta Salta Argentina", "https://www.facebook.com/groups/1418212825112195/"),
    ("OFERTAS DE MERCADO LIBRE 🏃", "https://www.facebook.com/groups/511618436673982/"),
    ("COMPRA Y VENTA SEGURA EN SALTA", "https://www.facebook.com/groups/1112022178829369/"),
    ("Comprás y ofertas de mercado libre", "https://www.facebook.com/groups/684857788022957/"),
    ("COMPRAS Y VENTAS , SALTA CAPITAL", "https://www.facebook.com/groups/1430015613904807/"),
    ("Ofertas y Remates Mercado Libre", "https://www.facebook.com/groups/1230158421395779/"),
    ("Mercado Libre Salta", "https://www.facebook.com/groups/417081242346033/"),
    ("OFERTAS ARGENTINAS", "(buscalo en Facebook por nombre)"),
    ("Ofertas y promociones Mercado libre ‼️", "https://www.facebook.com/groups/766445635841238/"),
    ("Ahorros, cupones, descuentos y promociones en ARGENTINA", "(buscalo por nombre)"),
    ("MeliOfertas ARG 🇦🇷 Cupones y Descuentos Mercado Libre", "(buscalo por nombre)"),
    ("MercadoLibre Argentina", "(buscalo por nombre)"),
]


def fmt(n): return "$ " + f"{round(n):,}".replace(",", ".")


def tg(method, **data):
    req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/{method}",
                                 data=urllib.parse.urlencode(data).encode())
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def _fernet():
    from cryptography.fernet import Fernet
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(("ojoalprecio-admin:" + TOKEN).encode()).digest()))


def admin_chat():
    if not ADMIN.exists(): return None
    try: return _fernet().decrypt(ADMIN.read_bytes()).decode()
    except Exception: return None


def enviar(texto):
    chat = admin_chat()
    if not chat:
        print("Todavía no hay chat del dueño registrado; no se envía el aviso."); return False
    tg("sendMessage", chat_id=chat, text=texto, disable_web_page_preview="true")
    print("aviso enviado"); return True


def registrar():
    """Busca un '/start <código>' cuyo hash coincida con config admin_code_hash."""
    want = CFG.get("admin_code_hash", "")
    if not want or admin_chat(): return
    ups = tg("getUpdates", timeout=0).get("result", [])
    for u in ups:
        m = u.get("message") or {}
        txt = (m.get("text") or "").strip()
        if m.get("chat", {}).get("type") == "private" and txt.startswith("/start "):
            code = txt.split(" ", 1)[1].strip()
            if hashlib.sha256(code.encode()).hexdigest() == want:
                ADMIN.write_bytes(_fernet().encrypt(str(m["chat"]["id"]).encode()))
                enviar("✅ Listo. Desde ahora te aviso por acá: los grupos del día (20:38) y si algo se rompe.")
                print("dueño registrado")
                break
    if ups: tg("getUpdates", offset=ups[-1]["update_id"] + 1, timeout=0)


def ofertas():
    prods = json.loads((ROOT / "docs" / "data.json").read_text(encoding="utf-8")).get("products", [])
    reales = sorted([p for p in prods if p["verdict"] == "real"], key=lambda p: -(p.get("off") or 0))
    nuevas = sorted([p for p in prods if p["verdict"] == "new"], key=lambda p: -(p.get("off") or 0))
    return (reales + nuevas)[:2]


def texto_oferta(p):
    precio = fmt(p["price"])
    if p.get("was"): precio += f" (antes {fmt(p['was'])}, {p['off']}% OFF)"
    return (f"🔥 Oferta de hoy en Mercado Libre: {p['name']}\n💰 {precio}\n🛒 {p['link']}\n"
            "📲 Todas las noches publico ofertas así en este canal gratis: t.me/ojoalprecionor")


def grupos():
    hoy = dt.datetime.now(AR).date()
    d = hoy.timetuple().tm_yday
    gi, gj = GRUPOS[(d * 2) % 14], GRUPOS[(d * 2 + 1) % 14]
    ofs = ofertas()
    if not ofs: return enviar("📣 Hoy no hay ofertas buenas para los grupos. No publiques nada.")
    a = ofs[0]; b = ofs[1] if len(ofs) > 1 else ofs[0]
    msg = [f"📣 Grupos de hoy ({hoy:%d/%m}). Publicá como la página Ojo al Precio, 1 vez por grupo:",
           "", f"1) {gi[0]}\n{gi[1]}", "", f"2) {gj[0]}\n{gj[1]}",
           "", "Te paso los textos en los 2 mensajes siguientes (mantené apretado → Copiar)."]
    extra = recordatorios(hoy)
    if extra: msg += ["", extra]
    enviar("\n".join(msg))
    enviar("Para el grupo 1:\n\n" + texto_oferta(a))
    if b is not a: enviar("Para el grupo 2:\n\n" + texto_oferta(b))


def recordatorios(hoy):
    if dt.date(2027, 1, 25) <= hoy <= dt.date(2027, 2, 6):
        return ("⚠️ Hay que renovar el token de la página de Facebook antes del 6/2 "
                "(los pasos están en el proyecto, doc ojo-al-precio). Si no, se cortan las publicaciones.")
    return ""


def gh_runs(wf):
    tok, repo = os.environ.get("GH_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not tok or not repo: return []
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/actions/workflows/{wf}/runs?per_page=10",
                                 headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode()).get("workflow_runs", [])


def salud():
    ahora = dt.datetime.now(AR); hoy = ahora.date().isoformat()
    tgp = json.loads((ROOT / "data" / "posted.json").read_text(encoding="utf-8"))
    fbp = json.loads((ROOT / "data" / "posted_fb.json").read_text(encoding="utf-8"))
    n_tg = sum(1 for v in tgp.values() if v == hoy)
    n_fb = sum(1 for v in fbp.values() if v == hoy)
    problemas = []
    if n_tg == 0: problemas.append("• Hoy no salió ninguna publicación en Telegram (¿token del bot vencido?).")
    if n_fb == 0: problemas.append("• Hoy no salió ninguna publicación en la página de Facebook (¿token de Facebook vencido?).")
    try:
        ok = [r for r in gh_runs("actualizar.yml") if r.get("conclusion") == "success"]
        if ok:
            ult = dt.datetime.fromisoformat(ok[0]["updated_at"].replace("Z", "+00:00"))
            if (dt.datetime.now(dt.timezone.utc) - ult).total_seconds() > 14 * 3600:
                problemas.append("• La web no se actualiza bien hace más de 14 h (revisá Actions → Actualizar ofertas; "
                                 "si dice token de Mercado Libre, hay que volver a autorizar).")
    except Exception as e:
        print("no pude revisar las corridas:", e)
    if problemas:
        enviar("🛠 Ojo al Precio necesita una mano:\n" + "\n".join(problemas))
    if ahora.weekday() == 0:  # lunes: resumen semanal
        desde = (ahora.date() - dt.timedelta(days=7)).isoformat()
        prods = json.loads((ROOT / "docs" / "data.json").read_text(encoding="utf-8")).get("products", [])
        reales = sum(1 for p in prods if p["verdict"] == "real")
        enviar(f"📊 Resumen semanal Ojo al Precio\n• Productos en la web: {len(prods)} ({reales} con descuento real)\n"
               f"• Productos publicados en 7 días: Telegram {sum(1 for v in tgp.values() if v >= desde)}, "
               f"Facebook {sum(1 for v in fbp.values() if v >= desde)}\n"
               f"• Estado: {'⚠️ ver aviso de arriba' if problemas else '✅ todo funcionando'}\n"
               "Mirá clics y ventas en el panel de afiliados de Mercado Libre.")
    print("salud:", "problemas" if problemas else "ok", n_tg, n_fb)


if __name__ == "__main__":
    if not TOKEN: sys.exit("Falta TELEGRAM_BOT_TOKEN")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "whoami": print("bot: @" + tg("getMe")["result"]["username"])
    elif cmd == "registrar": registrar()
    elif cmd == "grupos": grupos()
    elif cmd == "salud": salud()
    else: sys.exit(__doc__)
