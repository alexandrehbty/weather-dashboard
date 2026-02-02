"""
GeoMeteo (Flask) — Backend "senior pragmatique" adapté à Render FREE TIER

Différences vs ton fichier initial :contentReference[oaicite:1]{index=1} :
- HTTPS OpenWeather (pas HTTP)
- timeouts + retry/backoff (stabilité réseau)
- validation stricte city / lat / lon (400 propre)
- cache TTL en mémoire (évite spam OpenWeather, + rapide sur free-tier)
- rate limiting en mémoire (optionnel, conseillé)
- /health (à configurer comme Health Check Path sur Render)
- logs utiles avec request_id + durée (debug prod)
- mapping d’erreurs OpenWeather (401/404/429/5xx) vers des statuts cohérents
- headers sécurité basiques (sans dépendances lourdes)

Render Free Tier:
- pas de Redis requis
- cache en mémoire (perdu au redémarrage: OK en free-tier)
- logs = stdout, donc logging simple et structuré
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, g, send_file
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
# ✅ IMPORT DU CERVEAU (Lien avec ton fichier algo)
from algo import PortfolioBrain

load_dotenv()

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class Settings:
    api_key: str
    openweather_url: str = "https://api.openweathermap.org/data/2.5/weather"
        # ✅ URL Autocomplete (HTTPS)
    geocoding_url: str = "https://api.openweathermap.org/geo/1.0/direct"

    # Timeouts de base (utilisés seulement pour la connexion initiale)
    connect_timeout_s: float = float(os.getenv("CONNECT_TIMEOUT_S", "3"))

    # Config Retry
    retry_total: int = int(os.getenv("RETRY_TOTAL", "2"))
    retry_backoff_factor: float = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.4"))

    # Cache & Rate Limit
    cache_ttl_s: int = int(os.getenv("CACHE_TTL_S", "120"))
    cache_max_items: int = int(os.getenv("CACHE_MAX_ITEMS", "600"))
    rate_limit_enabled: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("1", "true", "yes", "on")
    rate_limit_default: str = os.getenv("RATE_LIMIT_DEFAULT", "120 per minute")
    rate_limit_get_weather: str = os.getenv("RATE_LIMIT_GET_WEATHER", "30 per minute")
    add_security_headers: bool = os.getenv("ADD_SECURITY_HEADERS", "true").lower() in ("1", "true", "yes", "on")


API_KEY = os.getenv("API_KEY", "")
settings = Settings(api_key=API_KEY)

app = Flask(__name__)
app.config["JSONIFY_PRETTYPRINT_REGULAR"] = False

# ✅ INITIALISATION DU CERVEAU (Mémoire globale)
brain = PortfolioBrain()

# -----------------------------------------------------------------------------
# Logging (stdout -> Render logs)
# -----------------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(message)s",  # logs "json-like" simples, Render friendly
)
logger = logging.getLogger("geometeo")

if not settings.api_key:
    logger.warning('{"level":"WARN","msg":"API_KEY manquante - /get_weather renverra 500 tant que non configurée"}')

# -----------------------------------------------------------------------------
# Optional: Rate limiting (memory) – FREE TIER friendly
# -----------------------------------------------------------------------------
limiter = None
if settings.rate_limit_enabled:
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address

        limiter = Limiter(
            get_remote_address,
            app=app,
            default_limits=[settings.rate_limit_default],
            storage_uri="memory://",  # pas de Redis requis (free-tier)
        )
        logger.info('{"level":"INFO","msg":"Rate limiting activé (mémoire)"}')
    except Exception as e:
        limiter = None
        logger.warning(
            '{"level":"WARN","msg":"Flask-Limiter non dispo ou erreur init; rate limit désactivé","detail":"%s"}',
            str(e).replace('"', "'"),
        )

# -----------------------------------------------------------------------------
# Requests session avec retry/backoff (stabilité réseau)
# -----------------------------------------------------------------------------
session = requests.Session()
retry = Retry(
    total=settings.retry_total,
    backoff_factor=settings.retry_backoff_factor,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=("GET",),
    raise_on_status=False,
)
adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
session.mount("https://", adapter)

# -----------------------------------------------------------------------------
# Cache mémoire TTL (simple, suffisant sur free tier)
# -----------------------------------------------------------------------------
# key -> (expires_at_epoch, payload)
_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    item = _cache.get(key)
    if not item:
        return None
    expires_at, payload = item
    if time.time() > expires_at:
        _cache.pop(key, None)
        return None
    return payload


def _cache_set(key: str, payload: Dict[str, Any]) -> None:
    # Eviction simple pour éviter de grossir indéfiniment en free tier
    if len(_cache) >= settings.cache_max_items:
        # supprime ~10% des entrées (simple et efficace)
        for i, k in enumerate(list(_cache.keys())):
            _cache.pop(k, None)
            if i >= max(1, settings.cache_max_items // 10):
                break
    _cache[key] = (time.time() + settings.cache_ttl_s, payload)


# -----------------------------------------------------------------------------
# Validation input (senior: éviter tout ce qui est "bizarre")
# -----------------------------------------------------------------------------
def _parse_city(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    city = raw.strip()
    if not city:
        return None
    if len(city) < 2 or len(city) > 64:
        return None
    return city


def _parse_lat_lon(raw_lat: Optional[str], raw_lon: Optional[str]) -> Optional[Tuple[float, float]]:
    if raw_lat is None or raw_lon is None:
        return None
    try:
        lat = float(raw_lat)
        lon = float(raw_lon)
    except ValueError:
        return None
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
        return None
    return lat, lon


def _cache_key(city: Optional[str], latlon: Optional[Tuple[float, float]]) -> str:
    if city:
        return f"city:{city.lower()}"
    assert latlon is not None
    # arrondi pour augmenter les hits cache sans trop dégrader
    return f"coord:{latlon[0]:.4f},{latlon[1]:.4f}"


# -----------------------------------------------------------------------------
# Mapping OpenWeather -> payload client
# -----------------------------------------------------------------------------
def _map_openweather(data: Dict[str, Any]) -> Dict[str, Any]:
    # accès défensif (évite KeyError si structure inattendue)
    weather0 = (data.get("weather") or [{}])[0] or {}
    main = data.get("main") or {}
    wind = data.get("wind") or {}
    sys = data.get("sys") or {}
    coord = data.get("coord") or {}

    return {
        "city": data.get("name", ""),
        "temperature": main.get("temp"),
        "description": weather0.get("description", ""),
        "icon": weather0.get("icon", ""),
        "feels_like": main.get("feels_like"),
        "wind_speed": wind.get("speed"),
        "humidity": main.get("humidity"),
        "pressure": main.get("pressure"),
        "visibility": data.get("visibility", 10000),
        "sunrise": sys.get("sunrise"),
        "sunset": sys.get("sunset"),
        "lat": coord.get("lat"),
        "lon": coord.get("lon"),
    }


# -----------------------------------------------------------------------------
# Request lifecycle: request_id + timing
# -----------------------------------------------------------------------------
@app.before_request
def _before_request() -> None:
    g.request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:12]
    g.start_time = time.time()


@app.after_request
def _after_request(response):
    # Basic security headers (lightweight, free-tier friendly)
    if settings.add_security_headers:
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        # Permissions-Policy minimaliste
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")

    # Corrélation côté client si tu veux debugger
    response.headers["X-Request-Id"] = getattr(g, "request_id", "unknown")

    # Log “1 ligne” par requête (Render-friendly)
    try:
        dur_ms = int((time.time() - g.start_time) * 1000)
    except Exception:
        dur_ms = -1

    logger.info(
        '{"level":"INFO","request_id":"%s","method":"%s","path":"%s","status":%s,"duration_ms":%s}',
        getattr(g, "request_id", "unknown"),
        request.method,
        request.path,
        response.status_code,
        dur_ms,
    )
    return response


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.route("/")
def home():
    # ✅ IMPORTANT : Pointe vers index.html (renomme ton fichier geometeo4.html)
    return render_template("index.html")

@app.route("/health")
def health():
    return "ok", 200

@app.route("/autocomplete")
def autocomplete():
    query = request.args.get("q", "").strip()
    if not query or len(query) < 2: return jsonify([])

    params = {"q": query, "limit": 5, "appid": settings.api_key}
    try:
        resp = requests.get(settings.geocoding_url, params=params, timeout=2.0)
        resp.raise_for_status()
        data = resp.json()
        suggestions = []
        for item in data:
            name = item.get('name')
            country = item.get('country')
            state = item.get('state', '')
            label = f"{name}, {state}, {country}" if state else f"{name}, {country}"
            suggestions.append({"label": label, "lat": item.get('lat'), "lon": item.get('lon')})
        return jsonify(suggestions)
    except Exception as e:
        logger.warning(f"Autocomplete error: {e}")
        return jsonify([])

@app.route("/get_weather")
def get_weather():
    # Rate limit spécifique sur cette route (si Flask-Limiter dispo)
    # (On l'applique via décorateur dynamique si possible)
    # NOTE: Flask ne permet pas facilement de "décorer" après définition,
    # donc on fait au plus simple: on déclare un wrapper plus bas si limiter présent.
    return _get_weather_impl()


def _get_weather_impl():
    # 1) Validation paramètres
    city = _parse_city(request.args.get("city"))
    latlon = _parse_lat_lon(request.args.get("lat"), request.args.get("lon"))

    if not city and not latlon:
        return jsonify({"error": "Veuillez fournir une ville valide ou des coordonnées valides."}), 400

    if not settings.api_key:
        return jsonify({"error": "Service mal configuré (API key manquante)."}), 500

    key = _cache_key(city, latlon)
    cached = _cache_get(key)
    if cached:
        payload = dict(cached)
        payload["_cached"] = True
        return jsonify(payload), 200

    params: Dict[str, Any] = {
        "appid": settings.api_key,
        "units": "metric",
        "lang": "fr",
    }

    if city:
        params["q"] = city
    else:
        assert latlon is not None
        params["lat"], params["lon"] = latlon


    # ✅ MODIF 1 : On demande au cerveau le timeout dynamique
    dynamic_timeout = brain.get_timeout()
    timeouts = (settings.connect_timeout_s, dynamic_timeout)

    # 2) Appel OpenWeather
    start = time.time()
    try:
        # ✅ CORRECTION : On utilise 'timeouts' (le dynamique) ici
        resp = session.get(
            settings.openweather_url,
            params=params,
            timeout=timeouts, 
        )
        
        # ✅ CALCUL LATENCE (pour le cerveau et les logs)
        latency = time.time() - start
        dur_ms = int(latency * 1000)

        # 3) Mapping codes OpenWeather
        # Pour le cerveau, une réponse HTTP (même 404 ou 500) = Le réseau marche (Success=True)
        
        if resp.status_code == 404:
            brain.update(latency, success=True) # ✅
            return jsonify({"error": "Ville introuvable."}), 404

        if resp.status_code == 401:
            brain.update(latency, success=True) # ✅
            logger.error(
                '{"level":"ERROR","request_id":"%s","msg":"OpenWeather unauthorized","duration_ms":%s}',
                getattr(g, "request_id", "unknown"), dur_ms,
            )
            return jsonify({"error": "Erreur de configuration côté serveur."}), 502

        if resp.status_code == 429:
            brain.update(latency, success=True) # ✅
            return jsonify({"error": "Service météo temporairement surchargé. Réessayez."}), 503

        if 500 <= resp.status_code <= 599:
            brain.update(latency, success=True) # ✅
            return jsonify({"error": "Service météo indisponible (erreur fournisseur)."}), 502

        resp.raise_for_status()
        
        # ✅ MODIF 2 : SUCCÈS -> On récompense le cerveau
        brain.update(latency, success=True)
        
        data = resp.json()
        weather = _map_openweather(data)

        if not weather.get("city") or weather.get("temperature") is None:
            logger.warning(
                '{"level":"WARN","request_id":"%s","msg":"Réponse OpenWeather inattendue","status":%s,"duration_ms":%s}',
                getattr(g, "request_id", "unknown"), resp.status_code, dur_ms,
            )
            return jsonify({"error": "Réponse inattendue du service météo."}), 502

        _cache_set(key, weather)
        return jsonify(weather), 200

    except requests.Timeout:
        # ✅ MODIF 3 : TIMEOUT -> On punit le cerveau (Backoff)
        latency = time.time() - start
        brain.update(latency, success=False)
        return jsonify({"error": "Le service météo met trop de temps à répondre."}), 504

    except requests.RequestException as e:
        # ✅ ERREUR RÉSEAU -> On punit aussi
        latency = time.time() - start
        brain.update(latency, success=False)
        
        logger.exception(
            '{"level":"ERROR","request_id":"%s","msg":"Erreur réseau OpenWeather","detail":"%s"}',
            getattr(g, "request_id", "unknown"), str(e).replace('"', "'"),
        )
        return jsonify({"error": "Erreur de connexion au service météo."}), 502

    except (ValueError, TypeError) as e:
        # Erreur JSON = Le réseau a marché, mais le contenu est pourri. On considère ça comme un succès réseau.
        latency = time.time() - start
        brain.update(latency, success=True) 
        
        logger.exception(
            '{"level":"ERROR","request_id":"%s","msg":"Réponse OpenWeather invalide","detail":"%s"}',
            getattr(g, "request_id", "unknown"), str(e).replace('"', "'"),
        )
        return jsonify({"error": "Réponse invalide du service météo."}), 502


# -----------------------------------------------------------------------------
# Apply route-specific rate limit if Limiter is available
# -----------------------------------------------------------------------------
if limiter is not None:
    # Décorateur appliqué à l’implémentation (pas à la route “shell”)
    _get_weather_impl = limiter.limit(settings.rate_limit_get_weather)(_get_weather_impl)

# -----------------------------------------------------------------------------
# Route pour télécharger le README (AJOUTÉ)
# -----------------------------------------------------------------------------
@app.route("/download/readme")
def download_readme():
    """Permet au recruteur de télécharger le README directement."""
    try:
        return send_file("README.md", as_attachment=True)
    except FileNotFoundError:
        return "README.md introuvable sur le serveur.", 404

# -----------------------------------------------------------------------------
# Local run (NE PAS utiliser en prod Render: utiliser gunicorn)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # En local seulement (Render utilise gunicorn + $PORT)
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "false").lower() in ("1", "true", "yes", "on")
    app.run(host="0.0.0.0", port=port, debug=debug)