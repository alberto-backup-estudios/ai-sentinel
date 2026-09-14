// AI Sentinel - Lógica de Interfaz, Filtros y Traducción al Español
(function() {
  // Estado de la aplicación
  let allArticles = [];
  let currentFilter = {
    category: 'all',
    thinker: null,
    language: 'all',
    search: '',
    onlySaved: false
  };
  let savedIds = new Set(JSON.parse(localStorage.getItem('ai_sentinel_saved') || '[]'));
  let isTranslateMode = localStorage.getItem('ai_sentinel_translate') === 'true';
  let activeModalArticle = null;
  let modalShowingTranslation = false;

  // Elementos DOM
  const searchInput = document.getElementById('searchInput');
  const mobileSearchInput = document.getElementById('mobileSearchInput');
  const clearSearchBtn = document.getElementById('clearSearchBtn');
  const articlesGrid = document.getElementById('articlesGrid');
  const loadingState = document.getElementById('loadingState');
  const emptyState = document.getElementById('emptyState');
  const resultsCount = document.getElementById('resultsCount');
  const activeFilterTags = document.getElementById('activeFilterTags');
  const lastUpdatedText = document.getElementById('lastUpdatedText');
  const refreshBtn = document.getElementById('refreshBtn');
  const refreshIcon = document.getElementById('refreshIcon');
  const toggleBookmarksBtn = document.getElementById('toggleBookmarksBtn');
  const savedBadgeCount = document.getElementById('savedBadgeCount');
  const themeToggleBtn = document.getElementById('themeToggleBtn');
  const sunIcon = document.getElementById('sunIcon');
  const moonIcon = document.getElementById('moonIcon');
  const resetFiltersBtn = document.getElementById('resetFiltersBtn');

  // Traducción
  const translateToggleBtn = document.getElementById('translateToggleBtn');
  const translateStatusPill = document.getElementById('translateStatusPill');
  const sidebarTranslateSwitch = document.getElementById('sidebarTranslateSwitch');

  // Modal
  const previewModal = document.getElementById('previewModal');
  const modalTitle = document.getElementById('modalTitle');
  const modalSourceTime = document.getElementById('modalSourceTime');
  const modalBadges = document.getElementById('modalBadges');
  const modalSummary = document.getElementById('modalSummary');
  const modalExternalLink = document.getElementById('modalExternalLink');
  const modalBookmarkBtn = document.getElementById('modalBookmarkBtn');
  const modalBookmarkText = document.getElementById('modalBookmarkText');
  const modalTranslateBtn = document.getElementById('modalTranslateBtn');
  const modalTranslateBtnText = document.getElementById('modalTranslateBtnText');
  const closeModalBtn = document.getElementById('closeModalBtn');

  // Inicialización de Tema
  function initTheme() {
    const savedTheme = localStorage.getItem('ai_sentinel_theme');
    const isDark = savedTheme ? savedTheme === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
    setTheme(isDark);
  }

  function setTheme(isDark) {
    if (isDark) {
      document.documentElement.classList.add('dark');
      sunIcon.classList.remove('hidden');
      moonIcon.classList.add('hidden');
      localStorage.setItem('ai_sentinel_theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      sunIcon.classList.add('hidden');
      moonIcon.classList.remove('hidden');
      localStorage.setItem('ai_sentinel_theme', 'light');
    }
  }

  themeToggleBtn.addEventListener('click', () => {
    const isDark = document.documentElement.classList.contains('dark');
    setTheme(!isDark);
  });

  // Inicialización de Traducción
  function initTranslationUI() {
    sidebarTranslateSwitch.checked = isTranslateMode;
    updateTranslateToggleBtnUI();
  }

  function updateTranslateToggleBtnUI() {
    if (isTranslateMode) {
      translateStatusPill.textContent = 'ON';
      translateStatusPill.className = 'px-1.5 py-0.2 rounded text-[10px] uppercase font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30';
      translateToggleBtn.classList.add('border-indigo-500/50', 'bg-indigo-950/30');
    } else {
      translateStatusPill.textContent = 'OFF';
      translateStatusPill.className = 'px-1.5 py-0.2 rounded text-[10px] uppercase font-bold bg-slate-800 text-slate-400';
      translateToggleBtn.classList.remove('border-indigo-500/50', 'bg-indigo-950/30');
    }
  }

  function setTranslateMode(active) {
    isTranslateMode = active;
    sidebarTranslateSwitch.checked = active;
    localStorage.setItem('ai_sentinel_translate', active ? 'true' : 'false');
    updateTranslateToggleBtnUI();
    applyFilters();

    // Si se activa, traducir en lote los artículos visibles que aún no tengan traducción
    if (active) {
      batchTranslateVisibleArticles();
    }
  }

  translateToggleBtn.addEventListener('click', () => {
    setTranslateMode(!isTranslateMode);
  });

  sidebarTranslateSwitch.addEventListener('change', (e) => {
    setTranslateMode(e.target.checked);
  });

  // Traducir en segundo plano artículos visibles en inglés que no tengan traducción
  async function batchTranslateVisibleArticles() {
    const untranslated = allArticles.filter(a => a.language === 'en' && (!a.title_es || a.title_es === a.title)).slice(0, 25);
    if (untranslated.length === 0) return;

    try {
      const payload = {
        items: untranslated.map(a => ({ id: a.id, title: a.title, summary: a.summary }))
      };
      const res = await fetch('/api/translate-batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.translations) {
        for (const [artId, trans] of Object.entries(data.translations)) {
          const art = allArticles.find(a => a.id === artId);
          if (art) {
            art.title_es = trans.title_es;
            art.summary_es = trans.summary_es;
          }
        }
        applyFilters();
      }
    } catch (e) {
      console.warn('Error en traducción en lote:', e);
    }
  }

  // Formato de tiempo relativo
  function timeAgo(dateString) {
    if (!dateString) return 'Reciente';
    try {
      const now = new Date();
      const past = new Date(dateString);
      const diffMs = now - past;
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMins / 60);
      const diffDays = Math.floor(diffHours / 24);

      if (diffMins < 1) return 'Justo ahora';
      if (diffMins < 60) return `Hace ${diffMins} min`;
      if (diffHours < 24) return `Hace ${diffHours} h`;
      if (diffDays === 1) return 'Ayer';
      if (diffDays < 7) return `Hace ${diffDays} días`;
      return past.toLocaleDateString('es-ES', { day: 'numeric', month: 'short' });
    } catch {
      return 'Reciente';
    }
  }

  // Carga de datos de la API
  async function loadArticles(forceRefresh = false) {
    showLoading(true);
    try {
      if (forceRefresh) {
        refreshIcon.classList.add('animate-spin-fast');
        await fetch('/api/refresh', { method: 'POST' });
      }

      const res = await fetch('/api/articles?limit=250');
      const data = await res.json();
      allArticles = data.articles || [];

      if (data.last_updated) {
        lastUpdatedText.textContent = `Actualizado ${timeAgo(data.last_updated)}`;
      }

      updateBadges(data.stats || {});
      applyFilters();

      if (isTranslateMode) {
        batchTranslateVisibleArticles();
      }
    } catch (err) {
      console.error('Error cargando noticias:', err);
      resultsCount.textContent = 'Error de conexión con el servidor local.';
    } finally {
      showLoading(false);
      refreshIcon.classList.remove('animate-spin-fast');
    }
  }

  function showLoading(isLoading) {
    if (isLoading) {
      loadingState.classList.remove('hidden');
      articlesGrid.classList.add('hidden');
      emptyState.classList.add('hidden');
    } else {
      loadingState.classList.add('hidden');
      articlesGrid.classList.remove('hidden');
    }
  }

  // Actualizar contadores de categorías en la barra lateral
  function updateBadges(stats) {
    document.getElementById('badgeTotalCount').textContent = stats.total || allArticles.length;
    const byCat = stats.by_category || {};
    document.getElementById('badgeGovCount').textContent = byCat['gobernanza'] || 0;
    document.getElementById('badgeSafetyCount').textContent = byCat['seguridad'] || 0;
    document.getElementById('badgeSocCount').textContent = byCat['sociedad'] || 0;
    document.getElementById('badgeOsCount').textContent = byCat['opensource'] || 0;
    document.getElementById('badgeNewsCount').textContent = byCat['newsletter'] || 0;
    updateSavedBadge();
  }

  function updateSavedBadge() {
    savedBadgeCount.textContent = savedIds.size;
  }

  // Aplicar filtros locales
  function applyFilters() {
    let filtered = [...allArticles];

    // Solo guardados
    if (currentFilter.onlySaved) {
      filtered = filtered.filter(a => savedIds.has(a.id));
    }

    // Categoría
    if (currentFilter.category && currentFilter.category !== 'all') {
      filtered = filtered.filter(a => (a.categories || []).includes(currentFilter.category));
    }

    // Pensador
    if (currentFilter.thinker) {
      const tTarget = currentFilter.thinker.toLowerCase();
      filtered = filtered.filter(a => 
        (a.thinkers || []).some(t => t.toLowerCase().includes(tTarget)) ||
        (a.title || '').toLowerCase().includes(tTarget) ||
        (a.title_es || '').toLowerCase().includes(tTarget) ||
        (a.summary || '').toLowerCase().includes(tTarget) ||
        (a.summary_es || '').toLowerCase().includes(tTarget)
      );
    }

    // Idioma original
    if (currentFilter.language && currentFilter.language !== 'all') {
      filtered = filtered.filter(a => a.language === currentFilter.language);
    }

    // Búsqueda por texto
    if (currentFilter.search.trim()) {
      const qWords = currentFilter.search.toLowerCase().trim().split(/\s+/);
      filtered = filtered.filter(a => {
        const full = `${a.title} ${a.title_es || ''} ${a.summary} ${a.summary_es || ''} ${a.source} ${(a.thinkers || []).join(' ')}`.toLowerCase();
        return qWords.every(w => full.includes(w));
      });
    }

    renderArticles(filtered);
    renderFilterSummary(filtered.length);
  }

  // Renderizado del resumen de filtros activos
  function renderFilterSummary(count) {
    resultsCount.textContent = `${count} ${count === 1 ? 'noticia encontrada' : 'noticias encontradas'}`;
    activeFilterTags.innerHTML = '';

    const createTag = (label, onRemove) => {
      const span = document.createElement('span');
      span.className = 'inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 text-[11px] font-medium';
      span.textContent = label;
      const btn = document.createElement('button');
      btn.className = 'hover:text-white ml-0.5';
      btn.innerHTML = '&times;';
      btn.onclick = onRemove;
      span.appendChild(btn);
      return span;
    };

    if (isTranslateMode) {
      activeFilterTags.appendChild(createTag('🌐 Traducción automática a Español', () => {
        setTranslateMode(false);
      }));
    }

    if (currentFilter.onlySaved) {
      activeFilterTags.appendChild(createTag('⭐ Guardados', () => {
        currentFilter.onlySaved = false;
        toggleBookmarksBtn.classList.remove('bg-amber-500/20', 'text-amber-400', 'border-amber-500/40');
        applyFilters();
      }));
    }

    if (currentFilter.thinker) {
      activeFilterTags.appendChild(createTag(`Autor: ${currentFilter.thinker}`, () => {
        currentFilter.thinker = null;
        document.querySelectorAll('.thinker-card').forEach(c => c.classList.remove('ring-2', 'ring-indigo-500'));
        applyFilters();
      }));
    }

    if (currentFilter.category !== 'all') {
      const catNames = {
        gobernanza: 'Gobernanza & Leyes',
        seguridad: 'Seguridad & Riesgo',
        sociedad: 'Democracia & Sociedad',
        opensource: 'Código Abierto',
        newsletter: 'Newsletters'
      };
      activeFilterTags.appendChild(createTag(`Tema: ${catNames[currentFilter.category] || currentFilter.category}`, () => {
        setCategory('all');
      }));
    }

    if (currentFilter.search) {
      activeFilterTags.appendChild(createTag(`"${currentFilter.search}"`, () => {
        searchInput.value = '';
        mobileSearchInput.value = '';
        clearSearchBtn.classList.add('hidden');
        currentFilter.search = '';
        applyFilters();
      }));
    }
  }

  // Renderizado de las tarjetas de noticias
  function renderArticles(articles) {
    if (articles.length === 0) {
      articlesGrid.innerHTML = '';
      articlesGrid.classList.add('hidden');
      emptyState.classList.remove('hidden');
      return;
    }

    emptyState.classList.add('hidden');
    articlesGrid.classList.remove('hidden');

    articlesGrid.innerHTML = articles.map(art => {
      const isSaved = savedIds.has(art.id);
      const timeStr = timeAgo(art.published);
      const isEnglish = art.language === 'en';
      
      // Decidir si mostramos versión traducida o original
      const showSpanish = isTranslateMode || art.userToggledTranslate;
      const displayTitle = (showSpanish && art.title_es) ? art.title_es : art.title;
      const displaySummary = (showSpanish && art.summary_es) ? art.summary_es : art.summary;
      const isTranslatedNow = showSpanish && isEnglish && Boolean(art.title_es);

      // Badges de pensadores
      const thinkerBadges = (art.thinkers || []).map(t => {
        let cls = 'badge-thinker-harari';
        let icon = 'book-open';
        if (t.includes('Hinton')) { cls = 'badge-thinker-hinton'; icon = 'alert-octagon'; }
        else if (t.includes('Bengio')) { cls = 'badge-thinker-bengio'; icon = 'shield-check'; }
        else if (t.includes('LeCun')) { cls = 'badge-thinker-lecun'; icon = 'unlock'; }
        else if (t.includes('Russell')) { cls = 'badge-thinker-russell'; icon = 'cpu'; }
        return `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold ${cls}">
          <i data-lucide="${icon}" class="w-3 h-3"></i> ${t}
        </span>`;
      }).join(' ');

      // Tags de categoría
      const catTags = (art.categories || []).map(c => {
        const labels = {
          gobernanza: 'Gobernanza',
          seguridad: 'Seguridad',
          sociedad: 'Sociedad',
          opensource: 'Open Source',
          newsletter: 'Newsletter'
        };
        return `<span class="text-[10px] uppercase font-semibold text-slate-400 bg-slate-800/80 px-1.5 py-0.5 rounded border border-slate-700/60 cursor-pointer hover:text-white hover:bg-slate-700 transition" onclick="window.filterByCat('${c}')">#${labels[c] || c}</span>`;
      }).join(' ');

      return `
        <article class="article-card p-4 sm:p-5 rounded-2xl bg-slate-900/80 border border-slate-800/90 flex flex-col justify-between gap-3 group">
          
          <!-- Encabezado de la noticia -->
          <div class="space-y-2">
            <div class="flex flex-wrap items-center justify-between gap-2 text-xs">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="font-bold px-2 py-0.5 rounded-md bg-slate-800 text-slate-300 text-[11px] border border-slate-700/50">
                  ${art.source || 'Prensa'}
                </span>
                <span class="text-slate-500 text-[11px]">${timeStr}</span>
                <span class="text-slate-600">•</span>
                <span class="text-[10px] font-bold uppercase px-1.5 py-0.2 rounded bg-slate-800/50 text-slate-400">${art.language.toUpperCase()}</span>
                ${isTranslatedNow ? `
                  <span class="inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.2 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/30">
                    <i data-lucide="languages" class="w-2.5 h-2.5"></i> Traducido al español
                  </span>
                ` : ''}
              </div>
              <div class="flex items-center gap-1.5">
                ${thinkerBadges}
              </div>
            </div>

            <!-- Título -->
            <h3 class="article-title text-base sm:text-lg font-bold text-slate-100 group-hover:text-indigo-300 transition-colors leading-snug">
              <a href="${art.link}" target="_blank" rel="noopener noreferrer" class="hover:underline">
                ${displayTitle}
              </a>
            </h3>

            <!-- Resumen limpio -->
            <p class="article-summary text-xs sm:text-sm text-slate-400 leading-relaxed line-clamp-2">
              ${displaySummary || 'Haz clic para leer la noticia completa en la fuente original.'}
            </p>
          </div>

          <!-- Pie de tarjeta: Categorías y Acciones -->
          <div class="pt-2 border-t border-slate-800/60 flex flex-wrap items-center justify-between gap-2">
            <div class="flex items-center gap-1.5 flex-wrap">
              ${catTags}
            </div>

            <div class="flex items-center gap-2">
              ${isEnglish ? `
                <button 
                  class="px-2 py-1 rounded-lg border text-xs font-semibold transition flex items-center gap-1 ${showSpanish ? 'bg-indigo-600/20 text-indigo-300 border-indigo-500/40 hover:bg-indigo-600/30' : 'bg-slate-800/70 border-slate-700/60 text-slate-400 hover:text-white'}"
                  onclick="window.toggleArticleTranslate('${art.id}')"
                  title="${showSpanish ? 'Ver original en inglés' : 'Traducir al español'}"
                >
                  <i data-lucide="languages" class="w-3.5 h-3.5"></i>
                  <span class="text-[11px]">${showSpanish ? 'Original' : 'Traducir'}</span>
                </button>
              ` : ''}

              <button 
                class="p-1.5 rounded-lg border text-xs font-medium transition ${isSaved ? 'bg-amber-500/20 text-amber-300 border-amber-500/40' : 'bg-slate-800/70 border-slate-700/60 text-slate-400 hover:text-white'}"
                onclick="window.toggleSave('${art.id}')"
                title="${isSaved ? 'Quitar de guardados' : 'Guardar para después'}"
              >
                <i data-lucide="bookmark" class="w-3.5 h-3.5 ${isSaved ? 'fill-amber-400' : ''}"></i>
              </button>

              <button 
                class="px-2.5 py-1 rounded-lg bg-slate-800/90 hover:bg-slate-700/90 border border-slate-700/70 text-xs font-semibold text-slate-300 hover:text-white transition flex items-center gap-1.5"
                onclick="window.openPreview('${art.id}')"
              >
                <i data-lucide="eye" class="w-3.5 h-3.5 text-indigo-400"></i>
                <span>Vista previa</span>
              </button>

              <a 
                href="${art.link}" 
                target="_blank" 
                rel="noopener noreferrer" 
                class="px-2.5 py-1 rounded-lg bg-indigo-600/90 hover:bg-indigo-500 border border-indigo-500/50 text-xs font-semibold text-white transition flex items-center gap-1"
                title="Abrir en pestaña nueva"
              >
                <span>Fuente</span>
                <i data-lucide="external-link" class="w-3 h-3"></i>
              </a>
            </div>
          </div>

        </article>
      `;
    }).join('');

    if (window.lucide) {
      window.lucide.createIcons();
    }
  }

  // Funciones globales para acciones de la UI
  window.filterByCat = function(category) {
    setCategory(category);
  };

  window.toggleArticleTranslate = async function(articleId) {
    const art = allArticles.find(a => a.id === articleId);
    if (!art) return;

    if (!art.title_es || art.title_es === art.title) {
      // Solicitar traducción al backend
      try {
        const res = await fetch('/api/translate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: art.id, title: art.title, summary: art.summary })
        });
        const data = await res.json();
        if (data.title_es) {
          art.title_es = data.title_es;
          art.summary_es = data.summary_es;
        }
      } catch (e) {
        console.warn('Error traduciendo artículo:', e);
      }
    }

    art.userToggledTranslate = !art.userToggledTranslate;
    applyFilters();
  };

  window.toggleSave = function(articleId) {
    if (savedIds.has(articleId)) {
      savedIds.delete(articleId);
    } else {
      savedIds.add(articleId);
    }
    localStorage.setItem('ai_sentinel_saved', JSON.stringify(Array.from(savedIds)));
    updateSavedBadge();
    applyFilters();

    if (activeModalArticle && activeModalArticle.id === articleId) {
      updateModalBookmarkBtn();
    }
  };

  window.openPreview = function(articleId) {
    const art = allArticles.find(a => a.id === articleId);
    if (!art) return;
    activeModalArticle = art;
    modalShowingTranslation = isTranslateMode || art.userToggledTranslate || art.language === 'es';

    renderModalContent();

    if (previewModal.showModal) {
      previewModal.showModal();
    } else {
      previewModal.setAttribute('open', '');
    }

    if (window.lucide) window.lucide.createIcons();
  };

  function renderModalContent() {
    if (!activeModalArticle) return;
    const art = activeModalArticle;
    const isEnglish = art.language === 'en';

    const title = (modalShowingTranslation && art.title_es) ? art.title_es : art.title;
    const summary = (modalShowingTranslation && art.summary_es) ? art.summary_es : (art.summary || 'Sin resumen disponible.');

    modalTitle.textContent = title;
    modalSourceTime.innerHTML = `
      <span class="font-bold text-slate-200">${art.source}</span>
      <span>•</span>
      <span>${timeAgo(art.published)}</span>
      <span>•</span>
      <span class="uppercase font-bold">${art.language}</span>
      ${modalShowingTranslation && isEnglish ? '<span class="text-indigo-400 font-semibold">• Traducido al español</span>' : ''}
    `;

    modalSummary.textContent = summary;
    modalExternalLink.href = art.link;

    modalBadges.innerHTML = (art.thinkers || []).map(t => 
      `<span class="px-2 py-0.5 rounded-full text-xs font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">${t}</span>`
    ).join(' ') + (art.categories || []).map(c => 
      `<span class="px-2 py-0.5 rounded text-xs text-slate-400 bg-slate-800">#${c}</span>`
    ).join(' ');

    if (isEnglish) {
      modalTranslateBtn.classList.remove('hidden');
      modalTranslateBtnText.textContent = modalShowingTranslation ? 'Ver original en inglés' : 'Traducir al español';
    } else {
      modalTranslateBtn.classList.add('hidden');
    }

    updateModalBookmarkBtn();
    if (window.lucide) window.lucide.createIcons();
  }

  modalTranslateBtn.addEventListener('click', async () => {
    if (!activeModalArticle) return;
    const art = activeModalArticle;

    if (!art.title_es || art.title_es === art.title) {
      modalTranslateBtnText.textContent = 'Traduciendo...';
      try {
        const res = await fetch('/api/translate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: art.id, title: art.title, summary: art.summary })
        });
        const data = await res.json();
        if (data.title_es) {
          art.title_es = data.title_es;
          art.summary_es = data.summary_es;
        }
      } catch (e) {
        console.warn('Error en traducción de modal:', e);
      }
    }

    modalShowingTranslation = !modalShowingTranslation;
    renderModalContent();
  });

  function updateModalBookmarkBtn() {
    if (!activeModalArticle) return;
    const isSaved = savedIds.has(activeModalArticle.id);
    modalBookmarkText.textContent = isSaved ? 'Guardado en favoritos' : 'Guardar para después';
    modalBookmarkBtn.className = isSaved
      ? 'flex items-center gap-2 px-3 py-2 rounded-xl bg-amber-500/20 text-amber-300 border border-amber-500/40 text-xs font-semibold transition'
      : 'flex items-center gap-2 px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300 transition';
  }

  modalBookmarkBtn.addEventListener('click', () => {
    if (activeModalArticle) {
      window.toggleSave(activeModalArticle.id);
    }
  });

  closeModalBtn.addEventListener('click', () => {
    previewModal.close();
  });

  previewModal.addEventListener('click', (e) => {
    const dialogDimensions = previewModal.getBoundingClientRect();
    if (
      e.clientX < dialogDimensions.left ||
      e.clientX > dialogDimensions.right ||
      e.clientY < dialogDimensions.top ||
      e.clientY > dialogDimensions.bottom
    ) {
      previewModal.close();
    }
  });

  // Cambio de Categoría
  function setCategory(category) {
    currentFilter.category = category;
    document.querySelectorAll('#categoryNav .nav-btn').forEach(btn => {
      if (btn.dataset.category === category) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });
    applyFilters();
  }

  document.querySelectorAll('#categoryNav .nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      setCategory(btn.dataset.category);
    });
  });

  // Botones de Pensadores Clave
  document.querySelectorAll('.thinker-card').forEach(card => {
    card.addEventListener('click', () => {
      const thinker = card.dataset.thinkerFilter;
      if (currentFilter.thinker === thinker) {
        currentFilter.thinker = null;
        card.classList.remove('ring-2', 'ring-indigo-500');
      } else {
        document.querySelectorAll('.thinker-card').forEach(c => c.classList.remove('ring-2', 'ring-indigo-500'));
        currentFilter.thinker = thinker;
        card.classList.add('ring-2', 'ring-indigo-500');
      }
      applyFilters();
    });
  });

  // Selector de Idioma original
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilter.language = btn.dataset.lang;
      applyFilters();
    });
  });

  // Búsqueda en tiempo real
  function handleSearchInput(val) {
    currentFilter.search = val;
    if (val.trim()) {
      clearSearchBtn.classList.remove('hidden');
    } else {
      clearSearchBtn.classList.add('hidden');
    }
    applyFilters();
  }

  searchInput.addEventListener('input', (e) => {
    mobileSearchInput.value = e.target.value;
    handleSearchInput(e.target.value);
  });

  mobileSearchInput.addEventListener('input', (e) => {
    searchInput.value = e.target.value;
    handleSearchInput(e.target.value);
  });

  clearSearchBtn.addEventListener('click', () => {
    searchInput.value = '';
    mobileSearchInput.value = '';
    clearSearchBtn.classList.add('hidden');
    handleSearchInput('');
  });

  window.addEventListener('keydown', (e) => {
    if (e.key === '/' && document.activeElement !== searchInput && document.activeElement !== mobileSearchInput) {
      e.preventDefault();
      searchInput.focus();
    }
  });

  refreshBtn.addEventListener('click', () => {
    loadArticles(true);
  });

  toggleBookmarksBtn.addEventListener('click', () => {
    currentFilter.onlySaved = !currentFilter.onlySaved;
    if (currentFilter.onlySaved) {
      toggleBookmarksBtn.classList.add('bg-amber-500/20', 'text-amber-400', 'border-amber-500/40');
    } else {
      toggleBookmarksBtn.classList.remove('bg-amber-500/20', 'text-amber-400', 'border-amber-500/40');
    }
    applyFilters();
  });

  resetFiltersBtn.addEventListener('click', () => {
    currentFilter = {
      category: 'all',
      thinker: null,
      language: 'all',
      search: '',
      onlySaved: false
    };
    searchInput.value = '';
    mobileSearchInput.value = '';
    clearSearchBtn.classList.add('hidden');
    toggleBookmarksBtn.classList.remove('bg-amber-500/20', 'text-amber-400', 'border-amber-500/40');
    document.querySelectorAll('.thinker-card').forEach(c => c.classList.remove('ring-2', 'ring-indigo-500'));
    document.querySelectorAll('.lang-btn').forEach(b => b.classList.toggle('active', b.dataset.lang === 'all'));
    setCategory('all');
  });

  // Modal de Móvil / Tablet
  const mobileAccessBtn = document.getElementById('mobileAccessBtn');
  const mobileModal = document.getElementById('mobileModal');
  const closeMobileModalBtn = document.getElementById('closeMobileModalBtn');
  const copyLanUrlBtn = document.getElementById('copyLanUrlBtn');
  const lanUrlDisplay = document.getElementById('lanUrlDisplay');

  if (mobileAccessBtn && mobileModal) {
    mobileAccessBtn.addEventListener('click', async () => {
      try {
        const res = await fetch('/api/lan-info');
        const info = await res.json();
        if (info.movil_url) {
          lanUrlDisplay.textContent = info.movil_url;
          const qr = document.getElementById('qrCodeImg');
          if (qr) {
            qr.src = `https://api.qrserver.com/v1/create-qr-code/?size=140x140&data=${encodeURIComponent(info.movil_url)}`;
          }
        }
      } catch (e) {
        console.warn('Error obteniendo IP local:', e);
      }
      mobileModal.showModal();
      if (window.lucide) window.lucide.createIcons();
    });

    if (closeMobileModalBtn) {
      closeMobileModalBtn.addEventListener('click', () => {
        mobileModal.close();
      });
    }

    mobileModal.addEventListener('click', (e) => {
      const d = mobileModal.getBoundingClientRect();
      if (e.clientX < d.left || e.clientX > d.right || e.clientY < d.top || e.clientY > d.bottom) {
        mobileModal.close();
      }
    });

    if (copyLanUrlBtn) {
      copyLanUrlBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(lanUrlDisplay.textContent);
        copyLanUrlBtn.textContent = '¡Copiado!';
        setTimeout(() => { copyLanUrlBtn.textContent = 'Copiar'; }, 2000);
      });
    }
  }

  // Inicializar todo
  initTheme();
  initTranslationUI();
  loadArticles();

})();
