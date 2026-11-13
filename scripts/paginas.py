"""Genera páginas estáticas (para Google): una por categoría, la de Black Friday, sitemap y robots."""
import json, re, html, unicodedata, datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
BASE = "https://ojoalprecio-ar-nor.github.io/"
BF = dt.date(2026, 11, 27)
E = html.escape
_CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

def stats():
    """Contador de visitas GoatCounter (sin cookies). Se activa poniendo "goatcounter": "<código>" en config.json."""
    c = _CFG.get("goatcounter", "").strip()
    return f'<script data-goatcounter="https://{c}.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>' if c else ""

def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")

def fmt(n):
    return "$ " + f"{round(n):,}".replace(",", ".")

def css():
    m = "\n".join(re.findall(r"<style>(.*?)</style>", (DOCS / "index.html").read_text(encoding="utf-8"), re.S))
    extra = """
.crumbs{font-size:14px;margin:18px 0 6px}.crumbs a{color:inherit}
.seo{max-width:760px;color:var(--muted);font-size:15px;line-height:1.55;margin:28px 0}
.hist{display:block;text-align:center;font-size:14px;margin-top:8px;color:inherit}.chart{color:var(--accent,#e8590c);margin:20px 0}.facts{list-style:none;padding:0;display:grid;gap:6px}.catlinks{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 30px}.catlinks a{border:1px solid var(--line);border-radius:999px;padding:6px 12px;font-size:14px;color:inherit;text-decoration:none;background:var(--surface)}
.bfbox{background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:18px 20px;margin:18px 0}
.bfnum{font-size:42px;font-weight:900;color:var(--brand)}
.up{color:var(--warn);font-weight:700}.low{color:var(--good);font-weight:700}
"""
    return m + extra

HEAD = """<!doctype html><html lang="es-AR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{title}</title><meta name="description" content="{desc}"><link rel="canonical" href="{url}">
<meta property="og:title" content="{title}"><meta property="og:description" content="{desc}"><meta property="og:image" content="{base}portada.png">
<link rel="icon" href="{base}logo.png"><style>{css}</style></head><body>
<header class="top"><div class="wrap"><div class="brandrow"><a href="{base}" style="color:inherit;text-decoration:none" class="brandname">Ojo al <span>Precio</span></a></div>
<h1>{h1}</h1><p class="lede">{lede}</p>
<div class="status"><span class="pill live">Actualizado {upd}</span><a class="pill tg" href="https://t.me/ojoalprecionor" target="_blank" rel="noopener">✈️ Recibí las ofertas en Telegram</a></div></div></header>
<main><div class="wrap">"""
FOOT = """</div></main><footer><div class="wrap"><div>Precios y stock pueden cambiar; verificá siempre el precio final antes de comprar. <a href="{base}" style="color:inherit">Ver todas las ofertas</a></div>
<div style="font-size:12px;opacity:.8">Participamos del Programa de Afiliados de Mercado Libre.</div></div></footer>{stats}</body></html>"""

def pslug(p):
    return slug(" ".join(p["name"].split()[:8]))[:70].strip("-") + "-" + p["id"].lower()

def grafico(h):
    """Gráfico SVG simple del historial de precios."""
    pts = sorted(h.items())
    if len(pts) < 2: return ""
    vals = [v for _, v in pts]; lo, hi = min(vals), max(vals); rng = (hi - lo) or 1
    W, H, P = 600, 180, 20
    xy = [(P + i * (W - 2 * P) / (len(pts) - 1), H - P - (v - lo) / rng * (H - 2 * P)) for i, (_, v) in enumerate(pts)]
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in xy)
    d0, d1 = dt.date.fromisoformat(pts[0][0]).strftime("%d/%m"), dt.date.fromisoformat(pts[-1][0]).strftime("%d/%m")
    return (f'<svg viewBox="0 0 {W} {H + 20}" role="img" aria-label="Historial de precio" style="width:100%;max-width:640px;height:auto">'
            f'<polyline fill="none" stroke="currentColor" stroke-width="3" points="{path}"/>'
            + "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="currentColor"/>' for x, y in xy) +
            f'<text x="{P}" y="{H + 15}" font-size="13" fill="currentColor">{d0}</text>'
            f'<text x="{W - P}" y="{H + 15}" font-size="13" text-anchor="end" fill="currentColor">{d1}</text>'
            f'<text x="{P}" y="14" font-size="13" fill="currentColor">máx {fmt(hi)}</text>'
            f'<text x="{W - P}" y="14" font-size="13" text-anchor="end" fill="currentColor">mín {fmt(lo)}</text></svg>')

def card(p, extra=""):
    v = {"real": ("real", "✓ Descuento real"), "fake": ("fake", "⚠ Ojo")}.get(p["verdict"], ("real", "● En seguimiento"))
    img = f'<img src="{E(p["img"])}" alt="{E(p["name"])}" loading="lazy">' if p.get("img") else ""
    was = f'<span class="was">{fmt(p["was"])}</span>' if p.get("was") else ""
    off = f'<span class="off">{p["off"]}% OFF</span>' if p.get("off") else ""
    ship = "+ costo de envío" if p.get("free_ship") is False else "Envío gratis"
    return f"""<article class="card"><div class="thumb">{img}</div>
<div><div class="cat">{E(p["cat"])}</div><h3 class="name">{E(p["name"])}</h3></div>
<div class="prices">{was}<div class="now"><span class="desde">desde</span><b>{fmt(p["price"])}</b>{off}</div><div class="ship">{ship}</div>
{extra}<div class="verdict {v[0]}">{v[1]} · {E(p.get("note",""))}</div>
<a class="btn go" href="{E(p["link"])}" target="_blank" rel="noopener sponsored">Ver en Mercado Libre</a>
<a class="hist" href="{BASE}precio/{pslug(p)}/">📈 Ver historial de precio</a></div></article>"""

def page(path, url, title, desc, h1, lede, body, upd):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HEAD.format(title=E(title), desc=E(desc), url=url, base=BASE, css=css(), h1=h1, lede=lede, upd=upd) + body + FOOT.format(base=BASE, stats=stats()), encoding="utf-8")

def generar():
    data = json.loads((DOCS / "data.json").read_text(encoding="utf-8"))
    hist = json.loads((ROOT / "data" / "history.json").read_text(encoding="utf-8")) if (ROOT / "data" / "history.json").exists() else {}
    prods = data["products"]
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=-3)))
    upd = now.strftime("%d/%m %H:%M")
    cats = {}
    for p in prods: cats.setdefault(p["cat"], []).append(p)
    cats = dict(sorted(cats.items(), key=lambda kv: -len(kv[1])))
    links = "".join(f'<a href="{BASE}ofertas/{slug(c)}/">{E(c)} ({len(v)})</a>' for c, v in cats.items())
    urls = [BASE, BASE + "black-friday/"]
    mes = now.strftime("%m/%Y")
    # Páginas por categoría
    for c, lst in cats.items():
        s = slug(c); url = f"{BASE}ofertas/{s}/"; urls.append(url)
        lst = sorted(lst, key=lambda p: p["rank"])
        reales = sum(p["verdict"] == "real" for p in lst)
        top = ", ".join(p["name"].split(" ")[0] + " " + " ".join(p["name"].split(" ")[1:3]) for p in lst[:3])
        body = f'<p class="crumbs"><a href="{BASE}">Inicio</a> › {E(c)}</p><section class="grid">' + "".join(card(p) for p in lst) + "</section>"
        body += f'<p class="seo">Estas son las ofertas de <b>{E(c)}</b> entre los productos más vendidos de Mercado Libre, revisadas el {upd}. Seguimos el precio de cada producto todos los días para avisarte si el descuento es real o si subieron el precio antes de ponerle el cartel de oferta. Hoy hay {len(lst)} productos en seguimiento{f" y {reales} con descuento real comprobado" if reales else ""}.</p>'
        body += f'<h2>Otras categorías</h2><div class="catlinks">{links}</div>'
        page(DOCS / "ofertas" / s / "index.html", url, f"Ofertas de {c} hoy ({mes}) | Ojo al Precio",
             f"Las {len(lst)} ofertas más vendidas de {c} en Mercado Libre, con descuento real verificado. Actualizado {upd}.",
             f"Ofertas de <em>{E(c)}</em> hoy", f"Los más vendidos de {E(c)} en Mercado Libre, con el precio seguido día a día. {E(top)} y más.", body, upd)
    # Black Friday
    dias = (BF - now.date()).days
    seg = []
    for p in prods:
        h = {d: v for d, v in hist.get(p["id"], {}).items()}
        if not h: continue
        low_d, low = min(h.items(), key=lambda kv: kv[1])
        desde = min(h)
        seg.append((p, low, low_d, desde, len(h)))
    subieron = sorted([s for s in seg if s[4] >= 3 and s[0]["price"] > s[1] * 1.05], key=lambda s: -(s[0]["price"] / s[1]))
    reales = [s for s in seg if s[0]["verdict"] == "real"]
    inicio = min((s[3] for s in seg), default=now.date().isoformat())
    d0 = dt.date.fromisoformat(inicio).strftime("%d/%m")
    if dias > 0:
        estado = f'<div class="bfbox"><div class="bfnum">Faltan {dias} días</div><p>Black Friday en Argentina es el <b>viernes 27 de noviembre</b>. Desde el <b>{d0}</b> registramos todos los días el precio de <b>{len(seg)} productos</b> de Mercado Libre. Así, el 27 vas a poder ver si el "descuento" es real o si lo subieron antes.</p></div>'
    elif dias == 0:
        estado = '<div class="bfbox"><div class="bfnum">¡Hoy es Black Friday!</div><p>Compará cada oferta contra el precio más bajo que registramos en las últimas semanas.</p></div>'
    else:
        estado = '<div class="bfbox"><div class="bfnum">Black Friday terminó</div><p>Seguimos controlando precios todos los días.</p></div>'
    body = estado
    def extra(s):
        p, low, low_d, desde, n = s
        dd = dt.date.fromisoformat(low_d).strftime("%d/%m")
        if p["price"] > low * 1.05:
            return f'<div class="ship"><span class="up">↑ {round((p["price"]/low-1)*100)}% más caro</span> que el {dd} ({fmt(low)})</div>'
        return f'<div class="ship"><span class="low">Precio más bajo registrado:</span> {fmt(low)} ({dd}) · {n} {"día" if n == 1 else "días"} de datos</div>'
    if subieron:
        body += f'<h2>⚠ Subieron de precio antes de Black Friday</h2><p class="seo">Estos productos cuestan más que su precio más bajo de los últimos días. Si el 27 aparecen "con descuento", puede ser un descuento inflado.</p><section class="grid">' + "".join(card(s[0], extra(s)) for s in subieron[:24]) + "</section>"
    if reales:
        body += '<h2>✓ Con descuento real hoy</h2><section class="grid">' + "".join(card(s[0], extra(s)) for s in reales[:24]) + "</section>"
    otros = [s for s in sorted(seg, key=lambda s: s[0]["rank"]) if s not in subieron and s not in reales][:24]
    body += '<h2>Precios que estamos siguiendo</h2><section class="grid">' + "".join(card(s[0], extra(s)) for s in otros) + "</section>"
    body += f'<p class="seo">¿Cómo saber si una oferta de Black Friday es real? Muchas tiendas suben el precio de lista días antes para mostrar un porcentaje de descuento más grande. La única forma de saberlo es comparar contra el historial de precios del producto. Ojo al Precio registra el precio de los productos más vendidos de Mercado Libre todos los días y te muestra si el precio de hoy es realmente más bajo.</p><h2>Ofertas por categoría</h2><div class="catlinks">{links}</div>'
    page(DOCS / "black-friday" / "index.html", BASE + "black-friday/", "Black Friday 2026 Argentina: ¿descuento real o trucho? | Ojo al Precio",
         f"Seguimos el precio de {len(seg)} productos de Mercado Libre todos los días para que en Black Friday (27/11) sepas si el descuento es real o inflado.",
         "Black Friday: ¿descuento <em>real o trucho</em>?", "Registramos el precio de los más vendidos de Mercado Libre todos los días. Antes de comprar, fijate si el descuento es de verdad.", body, upd)
    # Una página por producto (historial de precio)
    mes_txt = now.strftime("%m/%Y")
    for p in prods:
        h = hist.get(p["id"], {})
        url = f"{BASE}precio/{pslug(p)}/"; urls.append(url)
        vals = list(h.values()) or [p["price"]]
        lo, hi = min(vals), max(vals)
        if p["verdict"] == "real": veredicto = f"✅ <b>Buen momento para comprar:</b> {E(p.get('note',''))}."
        elif p["price"] > lo * 1.05: veredicto = f"⚠️ <b>Hoy está {round((p['price']/lo-1)*100)}% más caro</b> que su precio más bajo registrado ({fmt(lo)}). Si podés, esperá."
        else: veredicto = "📊 El precio está estable. Lo seguimos todos los días para avisarte si baja."
        ld = json.dumps({"@context": "https://schema.org", "@type": "Product", "name": p["name"], "image": p.get("img", ""),
                         "offers": {"@type": "Offer", "priceCurrency": "ARS", "price": round(p["price"]), "url": p["link"],
                                    "availability": "https://schema.org/InStock"}}, ensure_ascii=False)
        body = (f'<p class="crumbs"><a href="{BASE}">Inicio</a> › <a href="{BASE}ofertas/{slug(p["cat"])}/">{E(p["cat"])}</a> › Historial de precio</p>'
                f'<script type="application/ld+json">{ld}</script>'
                f'<p class="seo" style="font-size:18px">{veredicto}</p>'
                f'<div class="chart">{grafico(h)}</div>'
                f'<ul class="facts"><li>💰 Precio de hoy: <b>{fmt(p["price"])}</b></li><li>⬇️ Más bajo registrado: <b>{fmt(lo)}</b></li>'
                f'<li>⬆️ Más alto registrado: <b>{fmt(hi)}</b></li><li>📅 Días de seguimiento: {len(h)}</li></ul>'
                f'<section class="grid">{card(p)}</section>'
                f'<p class="seo">¿Conviene comprar {E(p["name"])} ahora? Registramos su precio en Mercado Libre todos los días para que veas si el descuento es real o si lo subieron antes de una promo como Black Friday (27/11). Precio actualizado el {upd}.</p>'
                f'<p><a class="pill tg" href="https://t.me/ojoalprecionor">✈️ Avisos de ofertas gratis en Telegram</a></p>'
                f'<h2>Más ofertas</h2><div class="catlinks">{links}</div>')
        corto = " ".join(p["name"].split()[:9])
        page(DOCS / "precio" / pslug(p) / "index.html", url, f"{corto}: historial de precio ({mes_txt}) | Ojo al Precio",
             f"Precio de hoy {fmt(p['price'])}. Mínimo registrado {fmt(lo)}. Mirá el historial de precio de {corto} en Mercado Libre antes de comprar.",
             f"Historial de precio: <em>{E(corto)}</em>", "¿Está barato o lo subieron? Mirá cómo cambió el precio día a día.", body, upd)
    # Sitemap y robots
    hoy = now.date().isoformat()
    (DOCS / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
        "".join(f"<url><loc>{u}</loc><lastmod>{hoy}</lastmod><changefreq>daily</changefreq></url>\n" for u in urls) + "</urlset>\n", encoding="utf-8")
    (DOCS / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE}sitemap.xml\n", encoding="utf-8")
    # Enlaces en la portada (entre marcadores)
    idx = DOCS / "index.html"; s = idx.read_text(encoding="utf-8")
    bloque = f'<!--catlinks--><section class="seo-links" style="margin:30px 0"><h2 style="font-size:18px">Ofertas por categoría</h2><div class="catlinks">{links}</div></section><!--/catlinks-->'
    s = re.sub(r"<!--catlinks-->.*?<!--/catlinks-->", lambda m: bloque, s, flags=re.S)
    st = f"<!--stats-->{stats()}<!--/stats-->"
    if "<!--stats-->" in s: s = re.sub(r"<!--stats-->.*?<!--/stats-->", lambda m: st, s, flags=re.S)
    else: s = s.replace("</body>", st + "</body>", 1)
    idx.write_text(s, encoding="utf-8")
    indexnow(urls)
    return len(cats), len(seg), len(subieron)

INDEXNOW_KEY = "6f3b9c2e8a1d4f7b9e0c5a2d8f1b3e7c"

def indexnow(urls):
    """Avisa a Bing/Yandex (IndexNow) que hay páginas nuevas o actualizadas. Solo corre en GitHub Actions."""
    (DOCS / f"{INDEXNOW_KEY}.txt").write_text(INDEXNOW_KEY, encoding="utf-8")
    import os, urllib.request
    if not os.environ.get("GITHUB_ACTIONS"): return
    body = json.dumps({"host": "ojoalprecio-ar-nor.github.io", "key": INDEXNOW_KEY,
                       "keyLocation": f"{BASE}{INDEXNOW_KEY}.txt", "urlList": urls[:10000]}).encode()
    try:
        req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, headers={"Content-Type": "application/json; charset=utf-8"})
        with urllib.request.urlopen(req, timeout=20) as r: print("IndexNow:", r.status)
    except Exception as e: print("IndexNow falló:", e)

if __name__ == "__main__":
    print(generar())
