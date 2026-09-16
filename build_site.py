import os
import sys
import json
import time
import html
import re
import hashlib
from datetime import datetime, timezone
from urllib.parse import quote
import urllib.request
from concurrent.futures import ThreadPoolExecutor
import feedparser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "feeds_config.json")
CACHE_FILE = os.path.join(BASE_DIR, "cache.json")
TRANSLATIONS_FILE = os.path.join(BASE_DIR, "translations_cache.json")
OUTPUT_HTML = os.path.join(BASE_DIR, "index.html")

THINKERS_RULES = {
    "Yuval Noah Harari": [r"\bharari\b", r"\byuval\b", r"\bnexus\b"],
    "Geoffrey Hinton": [r"\bgeoffrey hinton\b", r"\bhinton\b"],
    "Yoshua Bengio": [r"\byoshua bengio\b", r"\bbengio\b"],
    "Yann LeCun": [r"\byann lecun\b", r"\blecun\b", r"\ble cun\b"],
    "Fei-Fei Li": [r"\bfei-fei li\b", r"\bfei fei li\b", r"\bfeifei li\b", r"\bstanford hai\b"],
    "Stuart Russell": [r"\bstuart russell\b", r"\brussell\b", r"\bhuman compatible\b"],
    "Mustafa Suleyman": [r"\bmustafa suleyman\b", r"\bsuleyman\b", r"\bthe coming wave\b"],
    "Daron Acemoglu": [r"\bdaron acemoglu\b", r"\bacemoglu\b", r"\bpower and progress\b"],
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
        r"\b[eé]tica\b", r"\bethics\b", r"\bempleo\b", r"\bsalario\b"
    ],
    "opensource": [
        r"\bopen source\b", r"\bc[oó]digo abierto\b", r"\babierto\b",
        r"\bmeta\b", r"\boscurantismo\b", r"\bopen-source\b"
    ]
}

def clean_html(raw_html):
    if not raw_html: return ""
    cleantext = re.sub(r"<[^>]+>", " ", raw_html)
    cleantext = html.unescape(cleantext)
    return re.sub(r"\s+", " ", cleantext).strip()

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
    if default_thinker: thinkers.add(default_thinker)
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

def translate_to_es(text):
    if not text or not text.strip(): return ""
    clean = text.strip()[:1500]
    
    # Intento 1: clients5.google.com con dict-chrome-ex (muy rápido y sin 429)
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

    # Intento 2: translate.googleapis.com con dict-chrome-ex
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

    # Intento 3: fallback con client=webapp
    try:
        url = "https://translate.googleapis.com/translate_a/single?client=webapp&sl=auto&tl=es&dt=t&q=" + quote(clean)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            res = "".join([part[0] for part in data[0] if part and part[0]])
            if res and res.strip():
                return res.strip()
    except Exception:
        pass

    return ""

def fetch_feed(feed_info):
    articles = []
    feed_url = feed_info.get("url")
    feed_name = feed_info.get("name", "Fuente")
    feed_id = feed_info.get("id", "")
    feed_lang = feed_info.get("language", "es")
    default_cat = feed_info.get("category", "")
    default_thinker = feed_info.get("default_thinker")
    try:
        parsed = feedparser.parse(feed_url, agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        for entry in getattr(parsed, "entries", [])[:25]:
            clean_t = clean_html(getattr(entry, "title", "Sin título"))
            title, source = extract_source_name(clean_t, feed_name)
            summary = clean_html(getattr(entry, "summary", "") or getattr(entry, "description", ""))
            if len(summary) > 350: summary = summary[:347] + "..."
            link = getattr(entry, "link", "#")
            pub_date = parse_date(entry)
            combined = f"{title} {summary}"
            art_id = hashlib.md5(f"{link}_{title}".encode("utf-8")).hexdigest()[:12]
            articles.append({
                "id": art_id,
                "title": title,
                "summary": summary,
                "link": link,
                "source": source,
                "language": feed_lang,
                "published": pub_date,
                "thinkers": identify_thinkers(combined, default_thinker),
                "categories": identify_categories(combined, default_cat)
            })
    except Exception as e:
        print(f"[WARN] Error en {feed_name}: {e}")
    return articles

def main():
    print("[*] Generando sitio estático para GitHub Pages...")
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        feeds = json.load(f).get("feeds", [])

    all_articles = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        for res in ex.map(fetch_feed, feeds):
            all_articles.extend(res)

    # Deduplicar
    seen = set()
    deduped = []
    for a in all_articles:
        norm = re.sub(r"[^a-zA-Z0-9]", "", a["title"].lower())[:50]
        if norm and norm not in seen:
            seen.add(norm)
            deduped.append(a)

    deduped.sort(key=lambda x: x["published"], reverse=True)

    # Cargar / guardar traducciones
    translations = {}
    if os.path.exists(TRANSLATIONS_FILE):
        try:
            with open(TRANSLATIONS_FILE, "r", encoding="utf-8") as f:
                translations = json.load(f)
        except Exception: pass

    # Filtrar todos los artículos en inglés que no tengan traducción válida
    untranslated = [
        a for a in deduped 
        if a["language"] == "en" and (a["id"] not in translations or not translations[a["id"]].get("title_es"))
    ]
    if untranslated:
        print(f"[*] Traduciendo {len(untranslated)} noticias en inglés al español...")
        def do_t(a):
            t_title = translate_to_es(a["title"])
            t_sum = translate_to_es(a["summary"]) if a.get("summary") else ""
            if t_title:
                return a["id"], {"title_es": t_title, "summary_es": t_sum or t_title}
            return a["id"], None

        with ThreadPoolExecutor(max_workers=4) as ex:
            for art_id, res in ex.map(do_t, untranslated):
                if res and res.get("title_es"):
                    translations[art_id] = res

    with open(TRANSLATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(translations, f, ensure_ascii=False, indent=2)

    for a in deduped:
        if a["language"] == "es":
            a["title_es"] = a["title"]
            a["summary_es"] = a["summary"]
        elif a["id"] in translations:
            t = translations[a["id"]]
            a["title_es"] = t.get("title_es") or a["title"]
            a["summary_es"] = t.get("summary_es") or a["summary"]
        else:
            a["title_es"] = a["title"]
            a["summary_es"] = a["summary"]

    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    raw_articles = json.dumps(deduped, ensure_ascii=False)

    template = f"""<!DOCTYPE html>
<html lang="es" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0">
  <meta name="theme-color" content="#020617">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <title>AI Sentinel | Seguridad, Gobernanza & Pensadores de la IA</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/lucide@latest"></script>
  <style>
    body {{ font-family: 'Plus Jakarta Sans', system-ui, sans-serif; }}
    .badge-thinker-harari {{ background: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.3); }}
    .badge-thinker-hinton {{ background: rgba(244, 63, 94, 0.15); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.3); }}
    .badge-thinker-bengio {{ background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }}
    .badge-thinker-lecun {{ background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }}
    .badge-thinker-feifei {{ background: rgba(236, 72, 153, 0.15); color: #f472b6; border: 1px solid rgba(236, 72, 153, 0.3); }}
    .badge-thinker-russell {{ background: rgba(6, 182, 212, 0.15); color: #22d3ee; border: 1px solid rgba(6, 182, 212, 0.3); }}
    .badge-thinker-suleyman {{ background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }}
    .badge-thinker-acemoglu {{ background: rgba(132, 204, 22, 0.15); color: #a3e635; border: 1px solid rgba(132, 204, 22, 0.3); }}
    dialog[open] {{ animation: fadeIn 0.15s ease-out; }}
    @keyframes fadeIn {{ from {{ opacity: 0; transform: scale(0.97); }} to {{ opacity: 1; transform: scale(1); }} }}
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen pb-16 antialiased">
  
  <!-- CABECERA PRINCIPAL (ADAPTABLE PC / TABLET / MÓVIL) -->
  <header class="sticky top-0 z-30 backdrop-blur-md bg-slate-950/85 border-b border-slate-800 px-4 lg:px-8 py-3.5">
    <div class="max-w-6xl mx-auto flex items-center justify-between gap-3">
      
      <div class="flex items-center gap-3">
        <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
          <i data-lucide="shield-alert" class="w-5 h-5 text-white"></i>
        </div>
        <div>
          <h1 class="text-base sm:text-lg font-bold text-white flex items-center gap-2 leading-tight">
            AI Sentinel
            <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">GitHub Pages</span>
          </h1>
          <p class="text-[11px] text-slate-400 hidden sm:block">Seguridad Humana, Gobernanza & Pensadores Clave</p>
        </div>
      </div>

      <!-- Acciones de cabecera -->
      <div class="flex items-center gap-2">
        <button id="langToggleBtn" class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-semibold transition bg-indigo-600/20 text-indigo-300 border-indigo-500/40">
          <i data-lucide="languages" class="w-3.5 h-3.5"></i>
          <span id="langToggleLabel">Español</span>
        </button>

        <button id="savedFilterBtn" class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs font-semibold text-slate-300 hover:text-amber-400 transition">
          <i data-lucide="bookmark" class="w-3.5 h-3.5"></i>
          <span class="hidden sm:inline">Guardados</span>
          <span id="savedCount" class="px-1.5 py-0.2 rounded-full bg-amber-500/20 text-amber-300 text-[10px] font-bold">0</span>
        </button>
      </div>

    </div>

    <!-- Buscador integrado -->
    <div class="max-w-6xl mx-auto mt-3">
      <div class="relative">
        <i data-lucide="search" class="w-4 h-4 text-slate-400 absolute left-3.5 top-2.5"></i>
        <input 
          type="text" 
          id="searchInput" 
          placeholder="Buscar noticia, concepto, regulación o autor..." 
          class="w-full pl-10 pr-9 py-2 rounded-xl bg-slate-900/90 border border-slate-800 text-xs sm:text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
        >
        <button id="clearSearch" class="hidden absolute right-3 top-2 text-slate-400 text-sm font-bold">&times;</button>
      </div>
    </div>
  </header>

  <!-- PENSADORES CLAVE (FILTROS HORIZONTALES) -->
  <section class="max-w-6xl mx-auto px-4 lg:px-8 pt-4 pb-2">
    <div class="flex items-center justify-between mb-2">
      <span class="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
        <i data-lucide="users" class="w-3.5 h-3.5 text-indigo-400"></i> Voces y Pensadores Clave
      </span>
      <span class="text-[11px] text-slate-500">Última sincronización: {now_str}</span>
    </div>

    <!-- Carrusel de pensadores -->
    <div class="flex items-center gap-2 overflow-x-auto pb-2 no-scrollbar text-xs">
      <button data-thinker="all" class="thinker-pill active shrink-0 px-3 py-2 rounded-xl bg-slate-800 text-white font-bold border border-slate-700 transition">
        Todos
      </button>
      <button data-thinker="Yuval Noah Harari" class="thinker-pill shrink-0 px-3 py-2 rounded-xl bg-slate-900/90 hover:bg-purple-950/30 text-purple-300 font-bold border border-slate-800 flex items-center gap-1.5 transition">
        <span>📚</span> Harari
      </button>
      <button data-thinker="Fei-Fei Li" class="thinker-pill shrink-0 px-3 py-2 rounded-xl bg-slate-900/90 hover:bg-pink-950/30 text-pink-300 font-bold border border-slate-800 flex items-center gap-1.5 transition">
        <span>🌸</span> Fei-Fei Li
      </button>
      <button data-thinker="Stuart Russell" class="thinker-pill shrink-0 px-3 py-2 rounded-xl bg-slate-900/90 hover:bg-cyan-950/30 text-cyan-300 font-bold border border-slate-800 flex items-center gap-1.5 transition">
        <span>⚙️</span> Stuart Russell
      </button>
      <button data-thinker="Geoffrey Hinton" class="thinker-pill shrink-0 px-3 py-2 rounded-xl bg-slate-900/90 hover:bg-rose-950/30 text-rose-300 font-bold border border-slate-800 flex items-center gap-1.5 transition">
        <span>🧠</span> Hinton
      </button>
      <button data-thinker="Yoshua Bengio" class="thinker-pill shrink-0 px-3 py-2 rounded-xl bg-slate-900/90 hover:bg-amber-950/30 text-amber-300 font-bold border border-slate-800 flex items-center gap-1.5 transition">
        <span>🛡️</span> Bengio
      </button>
      <button data-thinker="Mustafa Suleyman" class="thinker-pill shrink-0 px-3 py-2 rounded-xl bg-slate-900/90 hover:bg-blue-950/30 text-blue-300 font-bold border border-slate-800 flex items-center gap-1.5 transition">
        <span>🌊</span> Suleyman
      </button>
      <button data-thinker="Daron Acemoglu" class="thinker-pill shrink-0 px-3 py-2 rounded-xl bg-slate-900/90 hover:bg-lime-950/30 text-lime-300 font-bold border border-slate-800 flex items-center gap-1.5 transition">
        <span>🏛️</span> Acemoglu
      </button>
      <button data-thinker="Yann LeCun" class="thinker-pill shrink-0 px-3 py-2 rounded-xl bg-slate-900/90 hover:bg-emerald-950/30 text-emerald-300 font-bold border border-slate-800 flex items-center gap-1.5 transition">
        <span>🔓</span> LeCun
      </button>
    </div>

    <!-- Filtros temáticos -->
    <div class="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs mt-1">
      <button data-cat="all" class="cat-pill active shrink-0 px-2.5 py-1 rounded-lg bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 font-semibold">Todas las áreas</button>
      <button data-cat="gobernanza" class="cat-pill shrink-0 px-2.5 py-1 rounded-lg bg-slate-900 text-slate-400 border border-slate-800 hover:text-white">⚖️ Gobernanza & Leyes</button>
      <button data-cat="seguridad" class="cat-pill shrink-0 px-2.5 py-1 rounded-lg bg-slate-900 text-slate-400 border border-slate-800 hover:text-white">🛡️ Seguridad & Riesgo</button>
      <button data-cat="sociedad" class="cat-pill shrink-0 px-2.5 py-1 rounded-lg bg-slate-900 text-slate-400 border border-slate-800 hover:text-white">🗳️ Democracia & Sociedad</button>
      <button data-cat="opensource" class="cat-pill shrink-0 px-2.5 py-1 rounded-lg bg-slate-900 text-slate-400 border border-slate-800 hover:text-white">🔓 Open Source</button>
      <button data-cat="newsletter" class="cat-pill shrink-0 px-2.5 py-1 rounded-lg bg-slate-900 text-slate-400 border border-slate-800 hover:text-white">✉️ Newsletters</button>
    </div>
  </section>

  <!-- CONTENEDOR PRINCIPAL DE NOTICIAS -->
  <main class="max-w-6xl mx-auto px-4 lg:px-8 mt-3">
    <div class="flex items-center justify-between text-xs text-slate-500 mb-3">
      <span id="resultsCount" class="font-bold text-slate-300">Cargando...</span>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-3.5" id="cardsGrid"></div>
  </main>

  <!-- MODAL DE VISTA PREVIA -->
  <dialog id="modal" class="p-0 rounded-2xl bg-slate-900 text-slate-100 border border-slate-700 max-w-lg w-[92vw] shadow-2xl backdrop:bg-slate-950/80">
    <div class="p-6 space-y-4">
      <div class="flex justify-between items-start gap-2 border-b border-slate-800 pb-3">
        <div>
          <span id="mSource" class="text-xs font-bold text-indigo-400"></span>
          <h2 id="mTitle" class="text-base sm:text-lg font-bold text-white leading-snug mt-1"></h2>
        </div>
        <button onclick="document.getElementById('modal').close()" class="p-1.5 text-slate-400 hover:text-white text-lg font-bold">&times;</button>
      </div>
      <div id="mBadges" class="flex flex-wrap gap-1 text-[11px]"></div>
      <p id="mSummary" class="text-xs sm:text-sm leading-relaxed text-slate-300 bg-slate-950 p-4 rounded-xl border border-slate-800"></p>
      <div class="flex justify-between items-center pt-2">
        <button id="mBookmarkBtn" class="text-xs font-semibold px-3 py-2 rounded-xl bg-slate-800 text-slate-300 flex items-center gap-1.5">
          <i data-lucide="bookmark" class="w-3.5 h-3.5"></i>
          <span>Guardar</span>
        </button>
        <a id="mLink" href="#" target="_blank" class="text-xs font-semibold px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white flex items-center gap-1.5 shadow-md">
          <span>Abrir fuente original</span>
          <i data-lucide="external-link" class="w-3.5 h-3.5"></i>
        </a>
      </div>
    </div>
  </dialog>

  <script>
    const RAW_ARTICLES = {raw_articles};
    let isSpanish = true;
    let currentThinker = 'all';
    let currentCategory = 'all';
    let onlySaved = false;
    let searchQuery = '';
    let savedIds = new Set(JSON.parse(localStorage.getItem('ai_sentinel_gh_saved') || '[]'));
    let activeModalArt = null;

    function render() {{
      document.getElementById('savedCount').textContent = savedIds.size;
      let filtered = RAW_ARTICLES.filter(a => {{
        if (onlySaved && !savedIds.has(a.id)) return false;
        if (currentThinker !== 'all') {{
          const t = currentThinker.toLowerCase();
          const matchThinker = (a.thinkers || []).some(x => x.toLowerCase().includes(t)) ||
                              a.title.toLowerCase().includes(t) ||
                              (a.title_es && a.title_es.toLowerCase().includes(t));
          if (!matchThinker) return false;
        }}
        if (currentCategory !== 'all') {{
          if (!(a.categories || []).includes(currentCategory)) return false;
        }}
        if (searchQuery.trim()) {{
          const q = searchQuery.toLowerCase();
          const full = `${{a.title}} ${{a.title_es || ''}} ${{a.summary}} ${{a.summary_es || ''}} ${{a.source}}`.toLowerCase();
          if (!full.includes(q)) return false;
        }}
        return true;
      }});

      document.getElementById('resultsCount').textContent = `${{filtered.length}} ${{filtered.length === 1 ? 'noticia' : 'noticias'}}`;

      const grid = document.getElementById('cardsGrid');
      if (filtered.length === 0) {{
        grid.innerHTML = '<div class="col-span-2 p-12 text-center text-slate-500 text-sm">No hay noticias que coincidan con la búsqueda.</div>';
        return;
      }}

      grid.innerHTML = filtered.map(a => {{
        const title = isSpanish && a.title_es ? a.title_es : a.title;
        const summary = isSpanish && a.summary_es ? a.summary_es : a.summary;
        const isSaved = savedIds.has(a.id);
        const thinkerBadges = (a.thinkers || []).map(t => {{
          let cls = 'badge-thinker-harari';
          if (t.includes('Hinton')) cls = 'badge-thinker-hinton';
          else if (t.includes('Bengio')) cls = 'badge-thinker-bengio';
          else if (t.includes('LeCun')) cls = 'badge-thinker-lecun';
          else if (t.includes('Fei-Fei') || t.includes('Li')) cls = 'badge-thinker-feifei';
          else if (t.includes('Russell')) cls = 'badge-thinker-russell';
          else if (t.includes('Suleyman')) cls = 'badge-thinker-suleyman';
          else if (t.includes('Acemoglu')) cls = 'badge-thinker-acemoglu';
          return `<span class="px-2 py-0.5 rounded-md text-[10px] font-bold ${{cls}}">${{t}}</span>`;
        }}).join(' ');

        return `
          <article class="p-4 sm:p-5 rounded-2xl bg-slate-900/80 border border-slate-800 flex flex-col justify-between gap-3 hover:border-slate-700 transition">
            <div class="space-y-2">
              <div class="flex items-center justify-between text-xs gap-2">
                <span class="font-bold text-slate-400 bg-slate-800 px-2 py-0.5 rounded text-[11px] truncate max-w-[150px]">${{a.source}}</span>
                <div class="flex items-center gap-1 shrink-0">${{thinkerBadges}}</div>
              </div>
              <h3 class="text-sm sm:text-base font-bold text-slate-100 hover:text-indigo-300 transition leading-snug">
                <a href="${{a.link}}" target="_blank">${{title}}</a>
              </h3>
              <p class="text-xs sm:text-sm text-slate-400 line-clamp-2 leading-relaxed">${{summary || 'Toca para leer más...'}}</p>
            </div>
            <div class="flex items-center justify-between pt-2 border-t border-slate-800/80 text-xs">
              <div class="flex gap-1 text-[10px] text-slate-500">
                ${{(a.categories || []).map(c => `<span>#${{c}}</span>`).join(' ')}}
              </div>
              <div class="flex items-center gap-2">
                <button onclick="toggleSave('${{a.id}}')" class="p-1 rounded text-slate-400 ${{isSaved ? 'text-amber-400 font-bold' : ''}}">
                  ${{isSaved ? '⭐ Guardado' : '⭐'}}
                </button>
                <button onclick="openModal('${{a.id}}')" class="px-2.5 py-1 rounded bg-slate-800 text-slate-300 font-medium hover:bg-slate-700">Leer</button>
                <a href="${{a.link}}" target="_blank" class="px-2.5 py-1 rounded bg-indigo-600 text-white font-medium hover:bg-indigo-500">Fuente</a>
              </div>
            </div>
          </article>
        `;
      }}).join('');

      if (window.lucide) window.lucide.createIcons();
    }}

    function toggleSave(id) {{
      if (savedIds.has(id)) savedIds.delete(id);
      else savedIds.add(id);
      localStorage.setItem('ai_sentinel_gh_saved', JSON.stringify(Array.from(savedIds)));
      render();
    }}

    function openModal(id) {{
      const a = RAW_ARTICLES.find(x => x.id === id);
      if (!a) return;
      activeModalArt = a;
      document.getElementById('mSource').textContent = a.source;
      document.getElementById('mTitle').textContent = isSpanish && a.title_es ? a.title_es : a.title;
      document.getElementById('mSummary').textContent = isSpanish && a.summary_es ? a.summary_es : a.summary;
      document.getElementById('mLink').href = a.link;
      document.getElementById('mBadges').innerHTML = (a.thinkers || []).map(t => `<span class="px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300">${{t}}</span>`).join(' ');
      document.getElementById('modal').showModal();
      if (window.lucide) window.lucide.createIcons();
    }}

    document.getElementById('langToggleBtn').onclick = () => {{
      isSpanish = !isSpanish;
      document.getElementById('langToggleLabel').textContent = isSpanish ? 'Español' : 'Original (EN)';
      render();
    }};

    document.getElementById('savedFilterBtn').onclick = () => {{
      onlySaved = !onlySaved;
      document.getElementById('savedFilterBtn').classList.toggle('bg-amber-500/20', onlySaved);
      document.getElementById('savedFilterBtn').classList.toggle('text-amber-300', onlySaved);
      render();
    }};

    document.querySelectorAll('.thinker-pill').forEach(btn => {{
      btn.onclick = () => {{
        document.querySelectorAll('.thinker-pill').forEach(b => b.classList.remove('active', 'bg-slate-800', 'text-white'));
        btn.classList.add('active', 'bg-slate-800', 'text-white');
        currentThinker = btn.dataset.thinker;
        render();
      }};
    }});

    document.querySelectorAll('.cat-pill').forEach(btn => {{
      btn.onclick = () => {{
        document.querySelectorAll('.cat-pill').forEach(b => b.classList.remove('active', 'bg-indigo-600/30', 'text-indigo-300', 'border-indigo-500/40'));
        btn.classList.add('active', 'bg-indigo-600/30', 'text-indigo-300', 'border-indigo-500/40');
        currentCategory = btn.dataset.cat;
        render();
      }};
    }});

    const searchInput = document.getElementById('searchInput');
    const clearBtn = document.getElementById('clearSearch');
    searchInput.oninput = (e) => {{
      searchQuery = e.target.value;
      clearBtn.classList.toggle('hidden', !searchQuery);
      render();
    }};
    clearBtn.onclick = () => {{
      searchInput.value = '';
      searchQuery = '';
      clearBtn.classList.add('hidden');
      render();
    }};

    render();
  </script>
</body>
</html>
"""

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(template)

    print(f"[OK] index.html generado con éxito ({len(deduped)} noticias).")

if __name__ == "__main__":
    main()
