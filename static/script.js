document.addEventListener('DOMContentLoaded', () => {
  // ----------------------------
  // 0) Helpers (DOM safe)
  // ----------------------------
  const resultDiv = document.getElementById('weather-result');
  const cityInput = document.getElementById('city-input');
  const searchForm = document.getElementById('search-form');
  const searchBtn = document.getElementById('search-btn');

  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

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
  // 1) Menu mobile (A11Y + clavier)
  // ----------------------------
  const mobileMenu = document.getElementById('mobile-menu');
  const navMenu = document.getElementById('nav-menu');

  function closeMenu() {
    navMenu.classList.remove('active');
    mobileMenu.classList.remove('active');
    mobileMenu.setAttribute('aria-expanded', 'false');
  }

  function toggleMenu() {
    const isOpen = navMenu.classList.toggle('active');
    mobileMenu.classList.toggle('active', isOpen);
    mobileMenu.setAttribute('aria-expanded', String(isOpen));
  }

  mobileMenu.addEventListener('click', toggleMenu);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeMenu();
  });

  // ----------------------------
  // 2) State + config
  // ----------------------------
  const state = {
    requestSeq: 0,
    activeController: null
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
    if (q.city) return `city:${q.city.toLowerCase()}`;
    return `coord:${Number(q.lat).toFixed(4)},${Number(q.lon).toFixed(4)}`;
  }

  function getCache(q) {
    const key = cacheKeyForQuery(q);
    const entry = cache.get(key);
    if (!entry) return null;
    if (Date.now() > entry.expiresAt) { cache.delete(key); return null; }
    return entry.data;
  }

  function setCache(q, data) {
    const key = cacheKeyForQuery(q);
    cache.set(key, { expiresAt: Date.now() + CONFIG.CACHE_TTL_MS, data });
  }

  function buildWeatherUrl(paramsObj) {
    const url = new URL('/get_weather', window.location.origin);
    for (const [k, v] of Object.entries(paramsObj)) url.searchParams.set(k, String(v));
    return url.toString();
  }

  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
  function isRetriableStatus(status) { return status === 429 || (status >= 500 && status <= 599); }

  // ----------------------------
  // 3) fetchJsonWithTimeout "senior correct"
  // ----------------------------
  async function fetchJsonWithTimeout(url, { timeoutMs = CONFIG.TIMEOUT_MS, signal } = {}) {
    const controller = new AbortController();

    let timeoutId = null;
    const abortOnTimeout = () => controller.abort(new DOMException('Timeout', 'AbortError'));
    timeoutId = setTimeout(abortOnTimeout, timeoutMs);

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

  async function fetchWeatherSenior(query) {
    const cached = getCache(query);
    if (cached) return { ok: true, data: cached, fromCache: true };

    if (state.activeController) state.activeController.abort();
    const controller = new AbortController();
    state.activeController = controller;

    const seq = ++state.requestSeq;
    const url = buildWeatherUrl(query);

    for (let attempt = 0; attempt <= CONFIG.RETRY_MAX; attempt++) {
      try {
        const { res, data } = await fetchJsonWithTimeout(url, { timeoutMs: CONFIG.TIMEOUT_MS, signal: controller.signal });

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
        if (err.name === 'AbortError') return { ok: false, error: 'Requête annulée/expirée', aborted: true };

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
  // 4) UI rendering (safe DOM)
  // ----------------------------
  const weatherIcons = {
    "01d": "☀️", "01n": "🌙", "02d": "🌤️", "02n": "☁️",
    "03d": "☁️", "03n": "☁️", "04d": "☁️", "04n": "☁️",
    "09d": "🌧️", "09n": "🌧️", "10d": "🌦️", "10n": "🌧️",
    "11d": "🌩️", "11n": "🌩️", "13d": "🌨️", "13n": "🌨️",
    "50d": "🌫️", "50n": "🌫️"
  };

  function formatTime(ts) {
    const d = new Date(ts * 1000);
    return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  }

  function renderWeather(data) {
    clear(resultDiv);
    const emoji = weatherIcons[data.icon] || '❓';

    const weatherInfo = el('div', { className: 'weather-info' }, [
      el('h3', {}, [String(data.city || '')]),
      el('p', { style: 'text-align:center; font-size:3em; margin:10px 0;' }, [emoji]),
      el('p', { style: 'text-align:center; color: var(--text-color-light); font-size:1.2em;' }, [String(data.description || '')]),
    ]);

    const grid = el('div', { className: 'weather-data-grid' });

    const cards = [
      { emoji: '🌡️', label: 'Température', value: `${data.temperature}°C` },
      { emoji: '🍃', label: 'Vent', value: `${data.wind_speed} m/s` },
      { emoji: '💧', label: 'Humidité', value: `${data.humidity}%` },
      { emoji: '⏱️', label: 'Pression', value: `${data.pressure} hPa` },
      { emoji: '👁️', label: 'Visibilité', value: `${(data.visibility ?? 0) / 1000} km` },
      { emoji: '🌅', label: 'Lever', value: formatTime(data.sunrise) },
      { emoji: '🌇', label: 'Coucher', value: formatTime(data.sunset) },
    ];

    for (const c of cards) {
      grid.appendChild(
        el('div', { className: 'weather-card' }, [
          el('span', { className: 'emoji' }, [c.emoji]),
          el('strong', {}, [c.label]),
          el('span', {}, [String(c.value)]),
        ])
      );
    }

    resultDiv.appendChild(weatherInfo);
    resultDiv.appendChild(grid);
  }

  // ----------------------------
  // 5) Map
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
    map.flyTo([data.lat, data.lon], 10, { animate: true, duration: 1.5 });
  }

  // ----------------------------
  // 6) UX : persistance + hash
  // ----------------------------
  const STORAGE_KEY = 'geometeo:lastCity';

  function saveLastCity(city) { try { localStorage.setItem(STORAGE_KEY, city); } catch (_) {} }
  function loadLastCity() { try { return localStorage.getItem(STORAGE_KEY) || ''; } catch (_) { return ''; } }

  function setHashCity(city) {
    const value = encodeURIComponent(city);
    history.replaceState(null, '', `#city=${value}`);
  }

  function readHashCity() {
    const m = (location.hash || '').match(/#city=([^&]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  async function runQuery(query, { source = 'ui' } = {}) {
    setAriaBusy(true);
    searchBtn.disabled = true;
    setStatus('info', 'Chargement...');

    try {
      const result = await fetchWeatherSenior(query);

      if (result.ignored) return;

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
      setAriaBusy(false);
      searchBtn.disabled = false;
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
    await runQuery({ city }, { source: 'form' });
  });

  // ----------------------------
  // 7) Autocompletion (UX Senior)
  // ----------------------------
  const datalist = document.getElementById('city-suggestions');
  let debounceTimer;

  cityInput.addEventListener('input', (e) => {
    const val = e.target.value;
    
    // On ne cherche pas si moins de 3 lettres
    if (val.length < 3) return;

    // Debounce : On attend que l'utilisateur arrête d'écrire depuis 300ms
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(async () => {
        try {
            const res = await fetch(`/autocomplete?q=${encodeURIComponent(val)}`);
            if (!res.ok) return;
            
            const suggestions = await res.json();
            
            // On vide l'ancienne liste
            datalist.innerHTML = '';
            
            // On remplit avec les nouvelles propositions
            suggestions.forEach(item => {
                const option = document.createElement('option');
                option.value = item.label;
                datalist.appendChild(option);
            });
        } catch (err) {
            console.warn("Erreur autocomplete", err);
        }
    }, 300);
  });

  // Bootstrap
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