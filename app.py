"""
GeoMeteo (Flask) — Backend météo résilient optimisé pour environnements contraints.

Fonctionnalités clés :
- Appels OpenWeather en HTTPS via requests.Session (connection pooling + retries)
- Timeouts dynamiques pilotés par l'algorithme Jacobson/Karn (algo.PortfolioBrain)
- Cache LRU en mémoire avec TTL et verrouillage thread-safe
- Rate limiting en mémoire (Flask-Limiter)
- Logs JSON structurés avec corrélation X-Request-Id et mesure de latence monotone
- Headers de sécurité HTTP (CSP, HSTS, X-Frame-Options, nosniff, Permissions-Policy)
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

import requests
from dotenv import load_dotenv
from flask import Flask, g, has_request_context, jsonify, render_template, request, send_file
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from algo import PortfolioBrain

load_dotenv()


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    api_key: str
    openweather_url: str = "https://api.openweathermap.org/data/2.5/weather"
    geocoding_url: str = "https://api.openweathermap.org/geo/1.0/direct"

    connect_timeout_s: float = float(os.getenv("CONNECT_TIMEOUT_S", "3"))

    retry_total: int = int(os.getenv("RETRY_TOTAL", "2"))
    retry_backoff_factor: float = float(os.getenv("RETRY_BACKOFF_FACTOR", "0.4"))

    cache_ttl_s: int = int(os.getenv("CACHE_TTL_S", "120"))
    cache_max_items: int = int(os.getenv("CACHE_MAX_ITEMS", "600"))
    rate_limit_enabled: bool = _env_bool("RATE_LIMIT_ENABLED", True)
    rate_limit_default: str = os.getenv("RATE_LIMIT_DEFAULT", "120 per minute")
    rate_limit_get_weather: str = os.getenv("RATE_LIMIT_GET_WEATHER", "30 per minute")
    add_security_headers: bool = _env_bool("ADD_SECURITY_HEADERS", True)


API_KEY = os.getenv("API_KEY", "")
settings = Settings(api_key=API_KEY)


# -----------------------------------------------------------------------------
# Logging JSON structuré (stdout)
# -----------------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(message)s")
logger = logging.getLogger("geometeo")


def _log_json(level: int, msg: str, exc_info: bool = False, **fields: Any) -> None:
    record: Dict[str, Any] = {
        "level": logging.getLevelName(level),
        "msg": msg,
    }
    if has_request_context():
        record["request_id"] = getattr(g, "request_id", "unknown")
    record.update(fields)
    logger.log(level, json.dumps(record, ensure_ascii=False), exc_info=exc_info)


# -----------------------------------------------------------------------------
# État partagé (algorithme, client HTTP, cache LRU thread-safe)
# -----------------------------------------------------------------------------
brain = PortfolioBrain()


def _build_http_session(cfg: Settings) -> requests.Session:
    http_session = requests.Session()
    retry = Retry(
        total=cfg.retry_total,
        backoff_factor=cfg.retry_backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    http_session.mount("https://", adapter)
    return http_session


session = _build_http_session(settings)

# Cache LRU en mémoire : key -> (expires_at_monotonic, payload)
_cache_lock = threading.Lock()
_cache: OrderedDict[str, Tuple[float, Dict[str, Any]]] = OrderedDict()


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    now = time.monotonic()
    with _cache_lock:
        item = _cache.get(key)
        if not item:
            return None
        expires_at, payload = item
        if now > expires_at:
            _cache.pop(key, None)
            return None
        _cache.move_to_end(key)
        return dict(payload)


def _cache_set(key: str, payload: Dict[str, Any], cfg: Settings = settings) -> None:
    max_items = max(1, cfg.cache_max_items)
    expires_at = time.monotonic() + cfg.cache_ttl_s
    with _cache_lock:
        _cache[key] = (expires_at, dict(payload))
        _cache.move_to_end(key)
        while len(_cache) > max_items:
            _cache.popitem(last=False)


# -----------------------------------------------------------------------------
# Helpers de validation, mapping et détection de retries
# -----------------------------------------------------------------------------
def _parse_city(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    city = raw.strip()
    if len(city) < 2 or len(city) > 64:
        return None
    return city


def _parse_lat_lon(
    raw_lat: Optional[str], raw_lon: Optional[str]
) -> Optional[Tuple[float, float]]:
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
    if latlon is not None:
        return f"coord:{latlon[0]:.4f},{latlon[1]:.4f}"
    if city:
        return f"city:{city.lower()}"
    return "unknown"


def _map_openweather(data: Dict[str, Any]) -> Dict[str, Any]:
    weather0 = (data.get("weather") or [{}])[0] or {}
    main = data.get("main") or {}
    wind = data.get("wind") or {}
    sys_data = data.get("sys") or {}
    coord = data.get("coord") or {}

    city_name = data.get("name", "")
    country = sys_data.get("country", "")
    display_city = f"{city_name}, {country}" if city_name and country else city_name

    return {
        "city": display_city,
        "temperature": main.get("temp"),
        "description": weather0.get("description", ""),
        "icon": weather0.get("icon", ""),
        "feels_like": main.get("feels_like"),
        "wind_speed": wind.get("speed"),
        "humidity": main.get("humidity"),
        "pressure": main.get("pressure"),
        "visibility": data.get("visibility", 10000),
        "sunrise": sys_data.get("sunrise"),
        "sunset": sys_data.get("sunset"),
        "lat": coord.get("lat"),
        "lon": coord.get("lon"),
    }


def _was_retried(resp: requests.Response) -> bool:
    """Détecte si urllib3 a effectué des retries (règle de Karn : ne pas polluer le SRTT)."""
    raw = getattr(resp, "raw", None)
    retries = getattr(raw, "retries", None)
    history = getattr(retries, "history", None)
    return isinstance(history, (list, tuple)) and len(history) > 0


def _init_limiter(flask_app: Flask, cfg: Settings) -> Any:
    if not cfg.rate_limit_enabled:
        return None
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address

        lim = Limiter(
            get_remote_address,
            app=flask_app,
            default_limits=[cfg.rate_limit_default],
            storage_uri="memory://",
        )
        _log_json(logging.INFO, "Rate limiting activé (mémoire)")
        return lim
    except Exception as exc:
        _log_json(
            logging.WARNING,
            "Flask-Limiter indisponible ; rate limiting désactivé",
            detail=str(exc),
        )
        return None


def _rate_limit(lim: Any, limit_rule: str) -> Callable:
    if lim is None:
        return lambda fn: fn
    return lim.limit(limit_rule)


# -----------------------------------------------------------------------------
# Flask Application Factory
# -----------------------------------------------------------------------------
limiter: Any = None


def create_app(cfg: Settings = settings) -> Flask:
    global limiter

    flask_app = Flask(__name__)
    flask_app.config["JSONIFY_PRETTYPRINT_REGULAR"] = False

    if not cfg.api_key:
        _log_json(
            logging.WARNING,
            "API_KEY manquante - /get_weather renverra 500 tant que non configurée",
        )

    app_limiter = _init_limiter(flask_app, cfg)
    limiter = app_limiter

    @flask_app.before_request
    def _before_request() -> None:
        g.request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:12]
        g.start_time = time.monotonic()

    @flask_app.after_request
    def _after_request(response):
        if cfg.add_security_headers:
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
            response.headers.setdefault(
                "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
            )
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; "
                "img-src 'self' https: data:; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://unpkg.com; "
                "script-src 'self' 'unsafe-inline' https://unpkg.com; "
                "connect-src 'self'; "
                "font-src https://fonts.gstatic.com;",
            )

        response.headers["X-Request-Id"] = getattr(g, "request_id", "unknown")

        start_time = getattr(g, "start_time", None)
        dur_ms = int((time.monotonic() - start_time) * 1000) if start_time is not None else -1

        _log_json(
            logging.INFO,
            "HTTP request completed",
            method=request.method,
            path=request.path,
            status=response.status_code,
            duration_ms=dur_ms,
        )
        return response

    @flask_app.route("/")
    def home():
        return render_template("index.html")

    @flask_app.route("/health")
    def health():
        return "ok", 200

    @flask_app.route("/algo/stats")
    def algo_stats():
        """Expose l'état interne de l'algorithme Jacobson/Karn (observabilité & E2E)."""
        return jsonify(brain.get_stats())

    @flask_app.route("/autocomplete")
    def autocomplete():
        query = request.args.get("q", "").strip()
        if len(query) < 2:
            return jsonify([])

        timeouts = (cfg.connect_timeout_s, brain.get_timeout())
        params = {"q": query, "limit": 5, "appid": cfg.api_key}
        start = time.monotonic()

        try:
            resp = session.get(cfg.geocoding_url, params=params, timeout=timeouts)
        except requests.RequestException as exc:
            latency = time.monotonic() - start
            brain.update(latency, success=False)
            _log_json(logging.WARNING, "Erreur réseau autocomplete", detail=str(exc))
            return jsonify([])

        latency = time.monotonic() - start
        if not _was_retried(resp):
            brain.update(latency, success=True)

        if resp.status_code >= 400:
            _log_json(
                logging.WARNING,
                "Erreur HTTP fournisseur autocomplete",
                status=resp.status_code,
            )
            return jsonify([])

        try:
            data = resp.json()
        except ValueError as exc:
            _log_json(logging.WARNING, "JSON invalide autocomplete", detail=str(exc))
            return jsonify([])

        suggestions = []
        for item in data:
            name = item.get("name")
            country = item.get("country")
            state = item.get("state", "")
            label = f"{name}, {state}, {country}" if state else f"{name}, {country}"
            suggestions.append(
                {"label": label, "lat": item.get("lat"), "lon": item.get("lon")}
            )

        return jsonify(suggestions)

    @flask_app.route("/get_weather")
    @_rate_limit(app_limiter, cfg.rate_limit_get_weather)
    def get_weather():
        city = _parse_city(request.args.get("city"))
        latlon = _parse_lat_lon(request.args.get("lat"), request.args.get("lon"))

        if not city and not latlon:
            return (
                jsonify({"error": "Veuillez fournir une ville valide ou des coordonnées valides."}),
                400,
            )

        if not cfg.api_key:
            return jsonify({"error": "Service mal configuré (API key manquante)."}), 500

        key = _cache_key(city, latlon)
        cached = _cache_get(key)
        if cached is not None:
            cached["_cached"] = True
            return jsonify(cached), 200

        params: Dict[str, Any] = {
            "appid": cfg.api_key,
            "units": "metric",
            "lang": "fr",
        }
        if latlon is not None:
            params["lat"], params["lon"] = latlon
        elif city:
            params["q"] = city

        timeouts = (cfg.connect_timeout_s, brain.get_timeout())
        start = time.monotonic()

        try:
            resp = session.get(cfg.openweather_url, params=params, timeout=timeouts)
        except requests.Timeout:
            latency = time.monotonic() - start
            brain.update(latency, success=False)
            return jsonify({"error": "Le service météo met trop de temps à répondre."}), 504
        except requests.RequestException as exc:
            latency = time.monotonic() - start
            brain.update(latency, success=False)
            _log_json(
                logging.ERROR,
                "Erreur réseau OpenWeather",
                exc_info=True,
                detail=str(exc),
            )
            return jsonify({"error": "Erreur de connexion au service météo."}), 502

        latency = time.monotonic() - start
        dur_ms = int(latency * 1000)

        if not _was_retried(resp):
            brain.update(latency, success=True)

        if resp.status_code == 404:
            return jsonify({"error": "Ville introuvable."}), 404

        if resp.status_code == 401:
            _log_json(logging.ERROR, "OpenWeather unauthorized", duration_ms=dur_ms)
            return jsonify({"error": "Erreur de configuration côté serveur."}), 502

        if resp.status_code == 429:
            return (
                jsonify({"error": "Service météo temporairement surchargé. Réessayez."}),
                503,
            )

        if resp.status_code >= 500:
            return jsonify({"error": "Service météo indisponible (erreur fournisseur)."}), 502

        if resp.status_code >= 400:
            _log_json(
                logging.WARNING,
                "Erreur client OpenWeather inattendue",
                status=resp.status_code,
                duration_ms=dur_ms,
            )
            return jsonify({"error": "Réponse inattendue du service météo."}), 502

        try:
            data = resp.json()
            weather = _map_openweather(data)
        except (ValueError, TypeError) as exc:
            _log_json(
                logging.ERROR,
                "Réponse OpenWeather invalide",
                exc_info=True,
                detail=str(exc),
            )
            return jsonify({"error": "Réponse invalide du service météo."}), 502

        # Préserve le nom de ville sélectionné par l'utilisateur lors d'une recherche GPS
        if city and latlon:
            weather["city"] = city

        if not weather.get("city") or weather.get("temperature") is None:
            _log_json(
                logging.WARNING,
                "Réponse OpenWeather incomplète",
                status=resp.status_code,
                duration_ms=dur_ms,
            )
            return jsonify({"error": "Réponse inattendue du service météo."}), 502

        _cache_set(key, weather, cfg)
        return jsonify(weather), 200

    @flask_app.route("/download/readme")
    def download_readme():
        """Permet de télécharger la documentation du projet."""
        readme_path = os.path.join(flask_app.root_path, "README.md")
        try:
            return send_file(readme_path, as_attachment=True)
        except FileNotFoundError:
            return "README.md introuvable sur le serveur.", 404

    return flask_app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = _env_bool("FLASK_DEBUG", False)
    app.run(host="0.0.0.0", port=port, debug=debug)