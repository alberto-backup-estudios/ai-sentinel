# -*- coding: utf-8 -*-
import os
import sys
import json
import time
import html
import re
import hashlib
from datetime import datetime, timezone
from http.server import HTTPServer, ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote
import urllib.request
from concurrent.futures import ThreadPoolExecutor
import feedparser

PORT = 8000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
CONFIG_FILE = os.path.join(BASE_DIR, "feeds_config.json")
CACHE_FILE = os.path.join(BASE_DIR, "cache.json")
TRANSLATIONS_FILE = os.path.join(BASE_DIR, "translations_cache.json")
CACHE_TTL = 1800  # 30 minutos

# Reglas de detección de pensadores
THINKERS_RULES = {
    "Yuval Noah Harari": [r"\bharari\b", r"\byuval\b", r"\bnexus\b"],
    "Geoffrey Hinton": [r"\bgeoffrey hinton\b", r"\bhinton\b"],
    "Yoshua Bengio": [r"\byoshua bengio\b", r"\bbengio\b"],
    "Yann LeCun": [r"\byann lecun\b", r"\blecun\b", r"\ble cun\b"],
    "Stuart Russell": [r"\bstuart russell\b", r"\brussell\b", r"\bhuman compatible\b"],
    "Tristan Harris": [r"\btristan harris\b", r"\baza raskin\b", r"\bhumane tech\b"]
}

CATEGORY_RULES = {
    "gobernanza": [
        r"\bgobernanza\b", r"\bgovernance\b", r"\bregulaci[oó]n\b", r"\bregulation\b",
        r"\bley\b", r"\blaw\b", r"\bparlamento\b", r"\btratado\b", r"\btreaty\b",
        r"\bpol[ií]tica[s]?\b", r"\bpolicy\b", r"\beu ai act\b", r"\bacta\b",
        r"\baisi\b", r"\blegislation\b", r"\bsummit\b", r"\boecd\b", r"\bcumbre\b"
    ],
    "seguridad": [
        r"\bseguridad\b", r"\bsafety\b", r"\briesgo[s]? existencial[es]?\b",
        r"\balineaci[oó]n\b", r"\balignment\b", r"\bcat[aá]strofe\b",
        r"\bsuperinteligencia\b", r"\bsuperintelligence\b", r"\bcontrol\b",
        r"\bapocalipsis\b", r"\bextinci[oó]n\b", r"\bx-risk\b", r"\bevaluaci[oó]n\b"
    ],
    "sociedad": [
        r"\bdemocracia\b", r"\bdemocracy\b", r"\bdesinformaci[oó]n\b", r"\bdisinformation\b",
        r"\bmanipulaci[oó]n\b", r"\bmanipulation\b", r"\bpsic[oó]pata\b",
        r"\belecciones\b", r"\belections\b", r"\bderechos\b", r"\brights\b",
        r"\bsesgo[s]?\b", r"\bbias\b", r"\bdeepfake[s]?\b", r"\bsociedad\b",
        r"\bsociety\b", r"\btrabajo\b", r"\blabor\b", r"\bnexus\b", r"\bhumano[s]?\b",
        r"\b[eé]tica\b", r"\bethics\b"
    ],
    "opensource": [
        r"\bopen source\b", r"\bc[oó]digo abierto\b", r"\babierto\b",
        r"\bmeta\b", r"\boscurantismo\b", r"\bopen-source\b"
    ]
}

def clean_html(raw_html):
    if not raw_html:
        return ""
    cleantext = re.sub(r"<[^>]+>", " ", raw_html)
    cleantext = html.unescape(cleantext)
    cleantext = re.sub(r"\s+", " ", cleantext).strip()
    return cleantext

def parse_date(entry):
    for attr in ["published_parsed", "updated_parsed", "created_parsed"]:
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc).isoformat()
            except Exception:
                pass
    return datetime.now(timezone.utc).isoformat()

def identify_thinkers(text, default_thinker=None):
    text_lower = text.lower()
    thinkers = set()
    if default_thinker:
        thinkers.add(default_thinker)
    for thinker, patterns in THINKERS_RULES.items():
        for pat in patterns:
            if re.search(pat, text_lower):
                thinkers.add(thinker)
                break
    return list(thinkers)

def identify_categories(text, default_cat=None):
    text_lower = text.lower()
    categories = set()
    if default_cat and default_cat != "pensadores":
        categories.add(default_cat)
    for cat, patterns in CATEGORY_RULES.items():
        for pat in patterns:
            if re.search(pat, text_lower):
                categories.add(cat)
                break
    if not categories and default_cat:
        categories.add(default_cat)
    return list(categories)

def extract_source_name(title, feed_name):
    if " - " in title:
        parts = title.rsplit(" - ", 1)
        if len(parts[1]) < 40 and not parts[1].endswith("."):
            return parts[0].strip(), parts[1].strip()
    return title, feed_name

# --- GESTOR DE TRADUCCIÓN AL ESPAÑOL ---
def load_translations_cache():
    if os.path.exists(TRANSLATIONS_FILE):
        try:
            with open(TRANSLATIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_translations_cache(cache):
    try:
        with open(TRANSLATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[WARN] Error guardando traducciones: {e}")

def translate_text_to_spanish(text):
    if not text or not text.strip(): return ""
    clean = text.strip()[:1500]
    
    try:
        url = "https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl=auto&tl=es&q=" + quote(clean)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
            if isinstance(data, list) and len(data) > 0:
                if isinstance(data[0], list) and len(data[0]) > 0 and data[0][0]:
                    return data[0][0]
                elif isinstance(data[0], str) and data[0]:
                    return data[0]
    except Exception:
        pass

    try:
        url = "https://translate.googleapis.com/translate_a/single?client=dict-chrome-ex&sl=auto&tl=es&dt=t&q=" + quote(clean)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            res = "".join([part[0] for part in data[0] if part and part[0]])
            if res and res.strip():
                return res.strip()
    except Exception:
        pass

    return clean

def translate_article(art_id, title, summary):
    cache = load_translations_cache()
    if art_id in cache:
        return cache[art_id]

    trans_title = translate_text_to_spanish(title) if title else ""
    trans_summary = translate_text_to_spanish(summary) if summary else ""

    item = {
        "title_es": trans_title,
        "summary_es": trans_summary
    }
    cache[art_id] = item
    save_translations_cache(cache)
    return item

def fetch_single_feed(feed_info):
    articles = []
    feed_url = feed_info.get("url")
    feed_name = feed_info.get("name", "Fuente")
    feed_id = feed_info.get("id", "")
    feed_lang = feed_info.get("language", "es")
    default_cat = feed_info.get("category", "")
    default_thinker = feed_info.get("default_thinker")

    try:
        parsed_feed = feedparser.parse(
            feed_url,
            agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
        entries = getattr(parsed_feed, "entries", [])
        for entry in entries[:30]:
            raw_title = getattr(entry, "title", "Sin título")
            clean_t = clean_html(raw_title)
            title, source_name = extract_source_name(clean_t, feed_name)

            raw_summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
            summary = clean_html(raw_summary)
            if len(summary) > 400:
                summary = summary[:397] + "..."

            link = getattr(entry, "link", "#")
            pub_date = parse_date(entry)

            combined_text = f"{title} {summary}"
            thinkers = identify_thinkers(combined_text, default_thinker)
            categories = identify_categories(combined_text, default_cat)

            unique_str = f"{link}_{title}"
            art_id = hashlib.md5(unique_str.encode("utf-8")).hexdigest()[:12]

            articles.append({
                "id": art_id,
                "title": title,
                "summary": summary,
                "link": link,
                "source": source_name,
                "feed_name": feed_name,
                "feed_id": feed_id,
                "language": feed_lang,
                "published": pub_date,
                "thinkers": thinkers,
                "categories": categories
            })
    except Exception as e:
        print(f"[ERROR] Error consultando {feed_name}: {e}", file=sys.stderr)

    return articles

def load_feeds_config():
    if not os.path.exists(CONFIG_FILE):
        return []
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("feeds", [])

def refresh_all_feeds():
    feeds = load_feeds_config()
    print(f"[*] Actualizando {len(feeds)} fuentes RSS en paralelo...")
    all_articles = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = executor.map(fetch_single_feed, feeds)
        for res in results:
            all_articles.extend(res)

    seen_titles = set()
    deduped = []
    for art in all_articles:
        norm = re.sub(r"[^a-zA-Z0-9áéíóúÁÉÍÓÚñÑ]", "", art["title"].lower())[:60]
        if norm and norm not in seen_titles:
            seen_titles.add(norm)
            deduped.append(art)

    deduped.sort(key=lambda x: x["published"], reverse=True)

    cache_data = {
        "timestamp": time.time(),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "count": len(deduped),
        "articles": deduped
    }

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)

    print(f"[OK] {len(deduped)} noticias procesadas y guardadas en caché.")
    return cache_data

def get_articles_data(force_refresh=False):
    if not force_refresh and os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                cache_time = data.get("timestamp", 0)
                if time.time() - cache_time < CACHE_TTL:
                    return data
        except Exception as e:
            print(f"[WARN] Error leyendo caché: {e}")

    return refresh_all_feeds()

class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            with open(os.path.join(STATIC_DIR, "index.html"), "rb") as f:
                self.wfile.write(f.read())
            return

        if path == "/movil" or path == "/movil.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            movil_path = os.path.join(STATIC_DIR, "movil.html")
            with open(movil_path, "rb") as f:
                self.wfile.write(f.read())
            return

        if path == "/download-movil" or path == "/ai_sentinel_movil.html":
            movil_path = os.path.join(STATIC_DIR, "movil.html")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="ai_sentinel_movil.html"')
            self.end_headers()
            with open(movil_path, "rb") as f:
                self.wfile.write(f.read())
            return

        if path == "/api/lan-info":
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(('8.8.8.8', 80))
                ip = s.getsockname()[0]
            except Exception:
                ip = '127.0.0.1'
            finally:
                s.close()
            info = {
                "local_ip": ip,
                "port": PORT,
                "lan_url": f"http://{ip}:{PORT}",
                "movil_url": f"http://{ip}:{PORT}/movil"
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(info, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/api/articles":
            params = parse_qs(parsed.query)
            cat = params.get("category", [None])[0]
            thinker = params.get("thinker", [None])[0]
            lang = params.get("lang", [None])[0]
            search = params.get("q", [None])[0]
            limit = int(params.get("limit", [150])[0])

            cache_data = get_articles_data()
            articles = cache_data.get("articles", [])
            translations = load_translations_cache()

            # Añadir traducciones disponibles a cada artículo
            for a in articles:
                if a["language"] == "es":
                    a["title_es"] = a["title"]
                    a["summary_es"] = a["summary"]
                elif a["id"] in translations:
                    t_item = translations[a["id"]]
                    a["title_es"] = t_item.get("title_es") or a["title"]
                    a["summary_es"] = t_item.get("summary_es") or a["summary"]

            # Filtrar
            if cat and cat != "all":
                articles = [a for a in articles if cat in a.get("categories", [])]

            if thinker and thinker != "all":
                articles = [a for a in articles if any(thinker.lower() in t.lower() for t in a.get("thinkers", []))]

            if lang and lang != "all":
                articles = [a for a in articles if a.get("language") == lang]

            if search:
                query_words = search.lower().split()
                def match(art):
                    full = f"{art.get('title','')} {art.get('title_es','')} {art.get('summary','')} {art.get('summary_es','')} {art.get('source','')} {' '.join(art.get('thinkers',[]))}".lower()
                    return all(w in full for w in query_words)
                articles = [a for a in articles if match(a)]

            stats = {
                "total": len(cache_data.get("articles", [])),
                "filtered": len(articles),
                "by_thinker": {},
                "by_category": {}
            }
            for a in cache_data.get("articles", []):
                for t in a.get("thinkers", []):
                    stats["by_thinker"][t] = stats["by_thinker"].get(t, 0) + 1
                for c in a.get("categories", []):
                    stats["by_category"][c] = stats["by_category"].get(c, 0) + 1

            response_payload = {
                "last_updated": cache_data.get("last_updated"),
                "total_articles": len(cache_data.get("articles", [])),
                "count": len(articles),
                "stats": stats,
                "articles": articles[:limit]
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(response_payload, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/api/stats":
            cache_data = get_articles_data()
            articles = cache_data.get("articles", [])
            stats = {
                "total": len(articles),
                "last_updated": cache_data.get("last_updated"),
                "by_thinker": {},
                "by_category": {},
                "by_source": {}
            }
            for a in articles:
                for t in a.get("thinkers", []):
                    stats["by_thinker"][t] = stats["by_thinker"].get(t, 0) + 1
                for c in a.get("categories", []):
                    stats["by_category"][c] = stats["by_category"].get(c, 0) + 1
                s = a.get("source", "Otro")
                stats["by_source"][s] = stats["by_source"].get(s, 0) + 1

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(stats, ensure_ascii=False).encode("utf-8"))
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/refresh":
            new_data = refresh_all_feeds()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "success",
                "count": new_data.get("count"),
                "last_updated": new_data.get("last_updated")
            }).encode("utf-8"))
            return

        if path == "/api/translate":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len).decode("utf-8")
            payload = json.loads(body)

            art_id = payload.get("id", "")
            title = payload.get("title", "")
            summary = payload.get("summary", "")

            translation = translate_article(art_id, title, summary)

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "success",
                "id": art_id,
                "title_es": translation["title_es"],
                "summary_es": translation["summary_es"]
            }, ensure_ascii=False).encode("utf-8"))
            return

        if path == "/api/translate-batch":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len).decode("utf-8")
            payload = json.loads(body)
            items = payload.get("items", [])

            results = {}
            def do_trans(item):
                art_id = item.get("id")
                t = translate_article(art_id, item.get("title"), item.get("summary"))
                return art_id, t

            with ThreadPoolExecutor(max_workers=6) as executor:
                for art_id, t in executor.map(do_trans, items):
                    results[art_id] = t

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "success",
                "translations": results
            }, ensure_ascii=False).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

def main():
    print("=" * 65)
    print("   AI SENTINEL: Seguridad, Gobernanza & Pensadores de la IA   ")
    print("=" * 65)
    print(f"[*] Directorio de trabajo: {BASE_DIR}")

    if not os.path.exists(CACHE_FILE):
        print("[*] Primera ejecución: Recopilando noticias de fuentes RSS...")
        refresh_all_feeds()
    else:
        print("[*] Cargando noticias existentes en caché local...")

    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = '127.0.0.1'
    finally:
        s.close()

    server_address = ("", PORT)
    httpd = ThreadingHTTPServer(server_address, DashboardHandler)
    print(f"\n[+] Servidor activo y escuchando en:")
    print(f"    - Desde esta PC:        http://localhost:{PORT}")
    print(f"    - Desde Tablet/Celular: http://{local_ip}:{PORT}")
    print(f"    - Versión móvil ligera: http://{local_ip}:{PORT}/movil\n")
    print("[+] Presione Ctrl+C en cualquier momento para detener el servidor.\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Servidor detenido por el usuario.")
        httpd.server_close()

if __name__ == "__main__":
    main()
