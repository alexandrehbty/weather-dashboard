document.addEventListener('DOMContentLoaded', () => {
  // ----------------------------
  // 0) Helpers (DOM safe)
  // ----------------------------
  const resultDiv = document.getElementById('weather-result');
  const cityInput = document.getElementById('city-input');
  const searchForm = document.getElementById('search-form');
  const searchBtn = document.getElementById('search-btn');

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function el(tag, props = {}, children = []) {
    const node = document.createElement(tag);
    Object.assign(node, props);
    for (const child of children) {
      if (child == null) continue;
      if (typeof child === 'string') node.appendChild(document.createTextNode(child));
      else node.appendChild(child);
    }
    return node;
  }

  function setAriaBusy(isBusy) {
    resultDiv.setAttribute('aria-busy', String(isBusy));
  }

  function setStatus(type, message) {
    clear(resultDiv);
    const color = type === 'error' ? 'var(--danger)' : 'var(--text-color-muted)';
    resultDiv.appendChild(el('p', { style: `text-align:center; color:${color};` }, [message]));
  }

  // ----------------------------
  // 1) Menu mobile (A11Y + clavier + tactile)
  // ----------------------------
  const mobileMenu = document.getElementById('mobile-menu');
  const navMenu = document.getElementById('nav-menu');

  function closeMenu() {
    if (!navMenu || !mobileMenu) return;
    navMenu.classList.remove('active');
    mobileMenu.classList.remove('active');
    mobileMenu.setAttribute('aria-expanded', 'false');
  }

  function toggleMenu() {
    if (!navMenu || !mobileMenu) return;
    const isOpen = navMenu.classList.toggle('active');
    mobileMenu.classList.toggle('active', isOpen);
    mobileMenu.setAttribute('aria-expanded', String(isOpen));
  }

  if (mobileMenu && navMenu) {
    mobileMenu.addEventListener('click', toggleMenu);

    navMenu.addEventListener('click', (e) => {
      if (e.target.closest('a')) closeMenu();
    });

    document.addEventListener('click', (e) => {
      if (
        navMenu.classList.contains('active') &&
        !navMenu.contains(e.target) &&
        !mobileMenu.contains(e.target)
      ) {
        closeMenu();
      }
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeMenu();
    });
  }

  // ----------------------------
  // 2) État + configuration
  // ----------------------------
  const state = {
    requestSeq: 0,
    uiSeq: 0,
    activeController: null,
    autocompleteController: null,
    lastMapClickAt: 0
  };

  const CONFIG = {
    TIMEOUT_MS: 12000,
    RETRY_MAX: 2,
    RETRY_BASE_DELAY_MS: 500,
    CACHE_TTL_MS: 2 * 60 * 1000,
    MAP_CLICK_THROTTLE_MS: 800
  };

  const cache = new Map();

  function cacheKeyForQuery(q) {
    if (q.lat != null && q.lon != null) {
      return `coord:${Number(q.lat).toFixed(4)},${Number(q.lon).toFixed(4)}`;
    }
    return `city:${String(q.city || '').toLowerCase()}`;
  }

  function getCache(q) {
    const key = cacheKeyForQuery(q);
    const entry = cache.get(key);
    if (!entry) return null;
    if (Date.now() > entry.expiresAt) {
      cache.delete(key);
      return null;
    }
    return entry.data;
  }

  function setCache(q, data) {
    const key = cacheKeyForQuery(q);
    cache.set(key, { expiresAt: Date.now() + CONFIG.CACHE_TTL_MS, data });
  }

  function buildWeatherUrl(paramsObj) {
    const url = new URL('/get_weather', window.location.origin);
    for (const [k, v] of Object.entries(paramsObj)) {
      if (v != null) url.searchParams.set(k, String(v));
    }
    return url.toString();
  }

  function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }

  function isRetriableStatus(status) {
    return status === 429 || (status >= 500 && status <= 599);
  }

  // ----------------------------
  // 3) Requêtes résilientes (timeout + retry + annulation)
  // ----------------------------
  async function fetchJsonWithTimeout(url, { timeoutMs = CONFIG.TIMEOUT_MS, signal } = {}) {
    const controller = new AbortController();
    const timeoutId = setTimeout(
      () => controller.abort(new DOMException('Timeout', 'AbortError')),
      timeoutMs
    );

    const onExternalAbort = () => controller.abort();
    if (signal) {
      if (signal.aborted) controller.abort();
      else signal.addEventListener('abort', onExternalAbort, { once: true });
    }

    try {
      const res = await fetch(url, { signal: controller.signal });
      const data = await res.json().catch(() => ({}));
      return { res, data };
    } finally {
      clearTimeout(timeoutId);
      if (signal) signal.removeEventListener('abort', onExternalAbort);
    }
  }

  async function fetchWeather(query) {
    const cached = getCache(query);
    if (cached) return { ok: true, data: cached, fromCache: true };

    if (state.activeController) state.activeController.abort();
    const controller = new AbortController();
    state.activeController = controller;

    const seq = ++state.requestSeq;
    const url = buildWeatherUrl(query);

    for (let attempt = 0; attempt <= CONFIG.RETRY_MAX; attempt++) {
      try {
        const { res, data } = await fetchJsonWithTimeout(url, {
          timeoutMs: CONFIG.TIMEOUT_MS,
          signal: controller.signal
        });

        if (seq !== state.requestSeq) return { ok: false, ignored: true };

        if (res.ok) {
          setCache(query, data);
          return { ok: true, data, fromCache: false };
        }

        if (isRetriableStatus(res.status) && attempt < CONFIG.RETRY_MAX) {
          await sleep(CONFIG.RETRY_BASE_DELAY_MS * Math.pow(2, attempt));
          continue;
        }

        return { ok: false, error: data?.error || `Erreur HTTP ${res.status}`, status: res.status };
      } catch (err) {
        if (seq !== state.requestSeq) return { ok: false, ignored: true };
        if (err.name === 'AbortError') {
          return { ok: false, error: 'Requête annulée/expirée', aborted: true };
        }

        if (attempt < CONFIG.RETRY_MAX) {
          await sleep(CONFIG.RETRY_BASE_DELAY_MS * Math.pow(2, attempt));
          continue;
        }
        return { ok: false, error: 'Erreur réseau. Vérifiez votre connexion.' };
      }
    }

    return { ok: false, error: 'Erreur inconnue.' };
  }

  // ----------------------------
  // 4) Rendu UI (DOM sécurisé)
  // ----------------------------
  const weatherIcons = {
    '01d': '☀️', '01n': '🌙', '02d': '🌤️', '02n': '☁️',
    '03d': '☁️', '03n': '☁️', '04d': '☁️', '04n': '☁️',
    '09d': '🌧️', '09n': '🌧️', '10d': '🌦️', '10n': '🌧️',
    '11d': '🌩️', '11n': '🌩️', '13d': '🌨️', '13n': '🌨️',
    '50d': '🌫️', '50n': '🌫️'
  };

  function formatTime(ts) {
    const num = Number(ts);
    if (!Number.isFinite(num) || num <= 0) return '—';
    return new Date(num * 1000).toLocaleTimeString('fr-FR', {
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  function renderWeather(data) {
    clear(resultDiv);
    const emoji = weatherIcons[data.icon] || '❓';

    const weatherInfo = el('div', { className: 'weather-info' }, [
      el('h3', {}, [String(data.city || '')]),
      el('p', { style: 'text-align:center; font-size:3em; margin:10px 0;' }, [emoji]),
      el(
        'p',
        { style: 'text-align:center; color: var(--text-color-light); font-size:1.2em;' },
        [String(data.description || '')]
      )
    ]);

    const grid = el('div', { className: 'weather-data-grid' });

    const cards = [
      { emoji: '🌡️', label: 'Température', value: `${data.temperature}°C` },
      { emoji: '🍃', label: 'Vent', value: `${data.wind_speed} m/s` },
      { emoji: '💧', label: 'Humidité', value: `${data.humidity}%` },
      { emoji: '⏱️', label: 'Pression', value: `${data.pressure} hPa` },
      { emoji: '👁️', label: 'Visibilité', value: `${(data.visibility ?? 0) / 1000} km` },
      { emoji: '🌅', label: 'Lever', value: formatTime(data.sunrise) },
      { emoji: '🌇', label: 'Coucher', value: formatTime(data.sunset) }
    ];

    for (const c of cards) {
      grid.appendChild(
        el('div', { className: 'weather-card' }, [
          el('span', { className: 'emoji' }, [c.emoji]),
          el('strong', {}, [c.label]),
          el('span', {}, [String(c.value)])
        ])
      );
    }

    resultDiv.appendChild(weatherInfo);
    resultDiv.appendChild(grid);
  }

  // ----------------------------
  // 5) Carte Leaflet + clic interactif
  // ----------------------------
  const map = L.map('map').setView([46.603354, 1.888334], 5);
  let currentMarker = null;

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap'
  }).addTo(map);

  function updateMap(data) {
    if (data.lat == null || data.lon == null) return;

    if (currentMarker) map.removeLayer(currentMarker);
    currentMarker = L.marker([data.lat, data.lon]).addTo(map);

    const popupNode = document.createElement('div');
    const b = document.createElement('b');
    b.textContent = String(data.city || '');
    popupNode.appendChild(b);
    popupNode.appendChild(document.createElement('br'));
    popupNode.appendChild(document.createTextNode(`${data.temperature}°C`));

    currentMarker.bindPopup(popupNode).openPopup();

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    map.flyTo([data.lat, data.lon], 10, {
      animate: !prefersReducedMotion,
      duration: 1.5
    });
  }

  map.on('click', (e) => {
    const now = Date.now();
    if (now - state.lastMapClickAt < CONFIG.MAP_CLICK_THROTTLE_MS) return;
    state.lastMapClickAt = now;

    const lat = Number(e.latlng.lat.toFixed(4));
    const lon = Number(e.latlng.lng.toFixed(4));
    runQuery({ lat, lon }, { source: 'map' });
  });

  // ----------------------------
  // 6) Persistance + hash URL + exécution
  // ----------------------------
  const STORAGE_KEY = 'geometeo:lastCity';

  function saveLastCity(city) {
    try { localStorage.setItem(STORAGE_KEY, city); } catch (_) {}
  }

  function loadLastCity() {
    try { return localStorage.getItem(STORAGE_KEY) || ''; } catch (_) { return ''; }
  }

  function setHashCity(city) {
    const value = encodeURIComponent(city);
    history.replaceState(null, '', `#city=${value}`);
  }

  function readHashCity() {
    const m = (location.hash || '').match(/#city=([^&]+)/);
    if (!m) return '';
    try {
      return decodeURIComponent(m[1]);
    } catch (_) {
      return '';
    }
  }

  async function runQuery(query, { source = 'ui' } = {}) {
    const uiSeq = ++state.uiSeq;
    setAriaBusy(true);
    searchBtn.disabled = true;
    setStatus('info', 'Chargement...');

    try {
      const result = await fetchWeather(query);

      if (result.ignored || uiSeq !== state.uiSeq) return;

      if (result.ok) {
        renderWeather(result.data);
        updateMap(result.data);

        if (result.data?.city) {
          cityInput.value = result.data.city;
          saveLastCity(result.data.city);
          setHashCity(result.data.city);
        }

        if (source === 'form') resultDiv.focus();
      } else {
        const msg = result.aborted
          ? 'La requête a expiré ou a été annulée. Réessayez.'
          : (result.error || 'Erreur lors de la récupération des données météo.');
        setStatus('error', msg);
        cityInput.focus();
      }
    } finally {
      if (uiSeq === state.uiSeq) {
        setAriaBusy(false);
        searchBtn.disabled = false;
      }
    }
  }

  searchForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const city = cityInput.value.trim();

    if (!city) {
      setStatus('error', 'Veuillez entrer un nom de ville.');
      cityInput.focus();
      return;
    }

    const matchedSuggestion = currentSuggestions.find((s) => s.label === city);

    if (matchedSuggestion) {
      await runQuery(
        {
          city: matchedSuggestion.label,
          lat: matchedSuggestion.lat,
          lon: matchedSuggestion.lon
        },
        { source: 'form' }
      );
    } else {
      await runQuery({ city }, { source: 'form' });
    }
  });

  // ----------------------------
  // 7) Autocomplétion
  // ----------------------------
  const datalist = document.getElementById('city-suggestions');
  let debounceTimer = null;
  let currentSuggestions = [];

  cityInput.addEventListener('input', (e) => {
    const val = e.target.value.trim();
    clearTimeout(debounceTimer);

    if (val.length < 3) {
      if (state.autocompleteController) state.autocompleteController.abort();
      currentSuggestions = [];
      clear(datalist);
      return;
    }

    debounceTimer = setTimeout(async () => {
      if (state.autocompleteController) state.autocompleteController.abort();
      const controller = new AbortController();
      state.autocompleteController = controller;

      try {
        const res = await fetch(`/autocomplete?q=${encodeURIComponent(val)}`, {
          signal: controller.signal
        });
        if (!res.ok) return;

        const suggestions = await res.json();
        if (!Array.isArray(suggestions)) return;

        currentSuggestions = suggestions;
        clear(datalist);

        suggestions.forEach((item) => {
          const option = document.createElement('option');
          option.value = item.label;
          datalist.appendChild(option);
        });
      } catch (err) {
        if (err.name !== 'AbortError') {
          console.warn('Erreur autocomplete', err);
        }
      }
    }, 300);
  });

  // ----------------------------
  // 8) Initialisation
  // ----------------------------
  const hashCity = readHashCity();
  const lastCity = hashCity || loadLastCity();

  if (lastCity) {
    cityInput.value = lastCity;
    setStatus('info', 'Chargement de la dernière ville…');
    runQuery({ city: lastCity }, { source: 'boot' });
  } else {
    setStatus('info', 'Entrez une ville ou cliquez sur la carte pour afficher la météo.');
  }
});