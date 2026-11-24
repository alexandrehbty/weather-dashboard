import math
import os
import sys
import threading
import unittest
from unittest.mock import MagicMock, patch

import requests

# Garantit la résolution des modules à la racine du projet
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import app as app_module
from algo import PortfolioBrain
from app import Settings, _cache, _cache_get, _cache_set, create_app


def _make_mock_response(
    status_code: int = 200,
    json_data=None,
    json_error: Exception | None = None,
    retried: bool = False,
) -> MagicMock:
    """Fabrique une réponse requests.Response factice propre et prévisible."""
    resp = MagicMock()
    resp.status_code = status_code
    if json_error is not None:
        resp.json.side_effect = json_error
    else:
        resp.json.return_value = json_data if json_data is not None else {}
    resp.raw.retries.history = (object(),) if retried else ()
    return resp


class TestPortfolioBrain(unittest.TestCase):
    """Tests unitaires de l'algorithme adaptatif Jacobson/Karn (RFC 6298)."""

    def setUp(self):
        self.now = 1000.0
        self.brain = PortfolioBrain(clock=lambda: self.now)

    def test_initial_values(self):
        self.assertEqual(self.brain.srtt, 3.0)
        self.assertEqual(self.brain.rttvar, 0.5)
        self.assertEqual(self.brain.get_timeout(), 5.0)

    def test_jacobson_update_success_converges_down(self):
        for _ in range(50):
            self.brain.update(observed_latency=0.1, success=True)
        self.assertLess(self.brain.get_timeout(), 2.0)
        self.assertGreaterEqual(self.brain.get_timeout(), PortfolioBrain.TIMEOUT_MIN)

    def test_karn_penalty_failure_doubles_timeout_up_to_cap(self):
        initial_timeout = self.brain.get_timeout()
        self.brain.update(observed_latency=10.0, success=False)
        expected = min(PortfolioBrain.TIMEOUT_MAX, initial_timeout * 2.0)
        self.assertEqual(self.brain.get_timeout(), expected)

    def test_rttvar_capped_under_prolonged_outage(self):
        """Vérifie que rttvar reste borné à RTTVAR_MAX même après 50 échecs consécutifs."""
        for _ in range(50):
            self.brain.update(observed_latency=5.0, success=False)

        self.assertEqual(self.brain.rttvar, PortfolioBrain.RTTVAR_MAX)
        self.assertEqual(self.brain.get_timeout(), PortfolioBrain.TIMEOUT_MAX)

    def test_soft_decay_after_inactivity(self):
        """Après MEMORY_TTL secondes d'inactivité, la variance s'élargit sans réinitialiser SRTT."""
        for _ in range(30):
            self.brain.update(observed_latency=0.2, success=True)

        srtt_before = self.brain.srtt
        rttvar_before = self.brain.rttvar
        timeout_before = self.brain.get_timeout()

        # Avance l'horloge simulée au-delà du TTL sans time.sleep()
        self.now += PortfolioBrain.MEMORY_TTL + 1.0
        timeout_after = self.brain.get_timeout()

        self.assertEqual(self.brain.srtt, srtt_before)
        self.assertGreater(self.brain.rttvar, rttvar_before)
        self.assertGreater(timeout_after, timeout_before)

        # Un appel immédiat suivant ne doit pas redéclencher le Soft Decay
        rttvar_once = self.brain.rttvar
        self.brain.get_timeout()
        self.assertEqual(self.brain.rttvar, rttvar_once)

    def test_invalid_observed_latencies_are_handled_safely(self):
        srtt_before = self.brain.srtt
        self.brain.update(observed_latency=math.nan, success=True)
        self.brain.update(observed_latency=math.inf, success=True)
        self.assertEqual(self.brain.srtt, srtt_before)

        # Une latence négative est ramenée à 0.0 sans faire planter l'algorithme
        self.brain.update(observed_latency=-2.5, success=True)
        self.assertGreaterEqual(self.brain.srtt, 0.0)
        self.assertTrue(math.isfinite(self.brain.get_timeout()))

    def test_get_stats_format(self):
        self.now += 12.34
        stats = self.brain.get_stats()
        self.assertEqual(set(stats.keys()), {"srtt", "rttvar", "timeout", "idle_sec"})
        self.assertEqual(stats["idle_sec"], 12.3)

    def test_thread_safety_under_concurrent_updates(self):
        errors = []

        def worker():
            try:
                for i in range(100):
                    self.brain.get_timeout()
                    self.brain.update(0.15 if i % 5 else 2.0, success=(i % 7 != 0))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        timeout = self.brain.get_timeout()
        self.assertGreaterEqual(timeout, PortfolioBrain.TIMEOUT_MIN)
        self.assertLessEqual(timeout, PortfolioBrain.TIMEOUT_MAX)


class TestCacheLRU(unittest.TestCase):
    """Tests unitaires du cache LRU thread-safe avec expiration TTL."""

    def setUp(self):
        _cache.clear()

    def tearDown(self):
        _cache.clear()

    def test_lru_evicts_least_recently_used(self):
        cfg = Settings(api_key="test-key", cache_max_items=2, cache_ttl_s=120)
        _cache_set("a", {"city": "A"}, cfg)
        _cache_set("b", {"city": "B"}, cfg)

        # Accéder à "a" le rend le plus récent -> "b" devient la cible d'éviction
        self.assertEqual(_cache_get("a"), {"city": "A"})

        _cache_set("c", {"city": "C"}, cfg)
        self.assertIsNotNone(_cache_get("a"))
        self.assertIsNone(_cache_get("b"))
        self.assertIsNotNone(_cache_get("c"))

    def test_ttl_expiration(self):
        cfg = Settings(api_key="test-key", cache_max_items=10, cache_ttl_s=60)
        with patch("app.time.monotonic", return_value=100.0):
            _cache_set("city:paris", {"city": "Paris"}, cfg)

        with patch("app.time.monotonic", return_value=159.0):
            self.assertEqual(_cache_get("city:paris"), {"city": "Paris"})

        with patch("app.time.monotonic", return_value=161.0):
            self.assertIsNone(_cache_get("city:paris"))


class TestGeoMeteoApp(unittest.TestCase):
    """Tests des routes Flask avec application isolée de .env et du rate limiting."""

    def setUp(self):
        _cache.clear()
        self.fresh_brain = PortfolioBrain()
        self.brain_patcher = patch.object(app_module, "brain", self.fresh_brain)
        self.brain_patcher.start()
        self.addCleanup(self.brain_patcher.stop)

        self.test_app = create_app(
            Settings(api_key="test-api-key", rate_limit_enabled=False)
        )
        self.client = self.test_app.test_client()

    def tearDown(self):
        _cache.clear()

    # --- Routes de base et observabilité ---

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"ok")

    def test_home_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<!DOCTYPE html>", response.data)

    def test_algo_stats_endpoint(self):
        response = self.client.get("/algo/stats")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.json.keys()), {"srtt", "rttvar", "timeout", "idle_sec"}
        )

    # --- Autocomplétion ---

    def test_autocomplete_short_query_returns_empty_without_http_call(self):
        with patch.object(app_module.session, "get") as mock_get:
            response = self.client.get("/autocomplete?q=a")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json, [])
            mock_get.assert_not_called()

    def test_autocomplete_success_formats_label(self):
        mock_resp = _make_mock_response(
            status_code=200,
            json_data=[
                {
                    "name": "Paris",
                    "country": "FR",
                    "state": "Ile-de-France",
                    "lat": 48.85,
                    "lon": 2.35,
                },
                {"name": "Monaco", "country": "MC", "lat": 43.73, "lon": 7.42},
            ],
        )
        with patch.object(app_module.session, "get", return_value=mock_resp) as mock_get:
            response = self.client.get("/autocomplete?q=Paris")

        self.assertEqual(response.status_code, 200)
        mock_get.assert_called_once()
        self.assertEqual(response.json[0]["label"], "Paris, Ile-de-France, FR")
        self.assertEqual(response.json[1]["label"], "Monaco, MC")

    def test_autocomplete_http_error_updates_brain_once_as_network_success(self):
        """Garantit l'absence de double appel brain.update() sur erreur HTTP 500."""
        mock_resp = _make_mock_response(status_code=500)
        with (
            patch.object(app_module.session, "get", return_value=mock_resp),
            patch.object(self.fresh_brain, "update") as mock_update,
        ):
            response = self.client.get("/autocomplete?q=Paris")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, [])
        mock_update.assert_called_once()
        self.assertTrue(mock_update.call_args.kwargs["success"])

    def test_autocomplete_network_error_penalizes_brain(self):
        with (
            patch.object(
                app_module.session,
                "get",
                side_effect=requests.exceptions.Timeout("timeout"),
            ),
            patch.object(self.fresh_brain, "update") as mock_update,
        ):
            response = self.client.get("/autocomplete?q=Paris")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, [])
        mock_update.assert_called_once()
        self.assertFalse(mock_update.call_args.kwargs["success"])

    # --- Validation des paramètres et configuration ---

    def test_missing_or_invalid_parameters_return_400(self):
        for url in (
            "/get_weather",
            "/get_weather?city=a",
            "/get_weather?lat=999&lon=2.35",
            "/get_weather?lat=abc&lon=def",
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 400)
                self.assertIn("Veuillez fournir une ville valide", response.json["error"])

    def test_missing_api_key_returns_500(self):
        unconfigured_app = create_app(Settings(api_key="", rate_limit_enabled=False))
        response = unconfigured_app.test_client().get("/get_weather?city=Paris")
        self.assertEqual(response.status_code, 500)
        self.assertIn("API key manquante", response.json["error"])

    # --- Gestions d'erreurs amont (Unhappy Paths) ---

    def test_upstream_status_mapping(self):
        cases = [
            (404, 404, "Ville introuvable."),
            (401, 502, "Erreur de configuration"),
            (429, 503, "temporairement surchargé"),
            (500, 502, "Service météo indisponible"),
        ]
        for upstream_code, expected_status, expected_fragment in cases:
            with self.subTest(upstream_code=upstream_code):
                _cache.clear()
                mock_resp = _make_mock_response(status_code=upstream_code)
                with patch.object(app_module.session, "get", return_value=mock_resp):
                    response = self.client.get("/get_weather?city=Paris")
                self.assertEqual(response.status_code, expected_status)
                self.assertIn(expected_fragment, response.json["error"])

    def test_api_timeout_error_returns_504(self):
        with patch.object(
            app_module.session,
            "get",
            side_effect=requests.exceptions.Timeout("timeout"),
        ):
            response = self.client.get("/get_weather?city=Paris")
        self.assertEqual(response.status_code, 504)
        self.assertIn("met trop de temps à répondre", response.json["error"])

    def test_api_connection_error_returns_502(self):
        with patch.object(
            app_module.session,
            "get",
            side_effect=requests.exceptions.ConnectionError("network down"),
        ):
            response = self.client.get("/get_weather?city=Paris")
        self.assertEqual(response.status_code, 502)
        self.assertIn("Erreur de connexion", response.json["error"])

    def test_invalid_json_from_upstream_returns_502(self):
        mock_resp = _make_mock_response(status_code=200, json_error=ValueError("bad json"))
        with patch.object(app_module.session, "get", return_value=mock_resp):
            response = self.client.get("/get_weather?city=Paris")
        self.assertEqual(response.status_code, 502)
        self.assertIn("Réponse invalide", response.json["error"])

    def test_karn_rule_skips_brain_update_when_request_was_retried(self):
        """Ne pollue pas SRTT/RTTVAR quand urllib3 a effectué des retries."""
        mock_resp = _make_mock_response(
            status_code=200,
            json_data={"name": "Lyon", "main": {"temp": 14.0}},
            retried=True,
        )
        with (
            patch.object(app_module.session, "get", return_value=mock_resp),
            patch.object(self.fresh_brain, "update") as mock_update,
        ):
            response = self.client.get("/get_weather?city=Lyon")

        self.assertEqual(response.status_code, 200)
        mock_update.assert_not_called()

    # --- Cas nominaux, GPS et cache ---

    def test_full_weather_api_logic(self):
        mock_resp = _make_mock_response(
            status_code=200,
            json_data={
                "weather": [{"description": "ciel clair", "icon": "01d"}],
                "main": {
                    "temp": 25.0,
                    "humidity": 40,
                    "pressure": 1013,
                    "feels_like": 24.0,
                },
                "sys": {"country": "FR", "sunrise": 1600000000, "sunset": 1600050000},
                "wind": {"speed": 5.0},
                "coord": {"lat": 43.3, "lon": 5.4},
                "name": "Marseille",
                "visibility": 10000,
            },
        )
        with patch.object(app_module.session, "get", return_value=mock_resp):
            response = self.client.get("/get_weather?city=Marseille")

        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertEqual(data["city"], "Marseille, FR")
        self.assertEqual(data["temperature"], 25.0)
        self.assertEqual(data["description"], "ciel clair")

    def test_gps_priority_preserves_selected_city_name(self):
        mock_resp = _make_mock_response(
            status_code=200,
            json_data={"name": "Station Quartier Nord", "main": {"temp": 18.5}},
        )
        with patch.object(app_module.session, "get", return_value=mock_resp) as mock_get:
            response = self.client.get("/get_weather?city=Paris&lat=48.8566&lon=2.3522")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["city"], "Paris")
        called_params = mock_get.call_args.kwargs["params"]
        self.assertEqual(called_params["lat"], 48.8566)
        self.assertEqual(called_params["lon"], 2.3522)
        self.assertNotIn("q", called_params)

    def test_caching_mechanism(self):
        mock_resp = _make_mock_response(
            status_code=200,
            json_data={"name": "Lyon", "main": {"temp": 10.0}},
        )
        with patch.object(app_module.session, "get", return_value=mock_resp) as mock_get:
            response1 = self.client.get("/get_weather?city=Lyon")
            response2 = self.client.get("/get_weather?city=Lyon")

        self.assertEqual(response1.status_code, 200)
        self.assertNotIn("_cached", response1.json)
        self.assertEqual(response2.status_code, 200)
        self.assertTrue(response2.json.get("_cached"))
        self.assertEqual(mock_get.call_count, 1)

    # --- Routes annexes et sécurité ---

    def test_download_readme(self):
        with self.client.get("/download/readme") as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn("attachment", response.headers.get("Content-Disposition", ""))
            self.assertIn(b"GeoMeteo", response.data)

    def test_security_and_correlation_headers(self):
        response = self.client.get("/")
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")
        self.assertIn("max-age=", response.headers.get("Strict-Transport-Security", ""))
        self.assertIn("default-src 'self'", response.headers.get("Content-Security-Policy", ""))
        self.assertIn("X-Request-Id", response.headers)


if __name__ == "__main__":
    unittest.main()