import unittest
from unittest.mock import patch, MagicMock
import time
import sys
import os
import requests

# Ajoute le dossier parent au path pour importer app et algo
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, _cache
from algo import PortfolioBrain

class TestPortfolioBrain(unittest.TestCase):
    """Test de l'intelligence artificielle (Jacobson/Karn)"""

    def setUp(self):
        self.brain = PortfolioBrain()

    def test_initial_values(self):
        self.assertEqual(self.brain.srtt, 3.0)
        self.assertEqual(self.brain.rttvar, 0.5)
        self.assertEqual(self.brain.get_timeout(), 5.0)

    def test_jacobson_update_success(self):
        for _ in range(50):
            self.brain.update(observed_latency=0.1, success=True)
        self.assertLess(self.brain.get_timeout(), 5.0)

    def test_karn_penalty_failure(self):
        initial_timeout = self.brain.get_timeout()
        self.brain.update(observed_latency=10.0, success=False)
        expected = min(10.0, initial_timeout * 2)
        self.assertEqual(self.brain.get_timeout(), expected)


class TestGeoMeteoApp(unittest.TestCase):
    """Test des routes Flask (API) adaptées au vrai app.py"""

    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        self.client = app.test_client()
        # On vide le cache avant chaque test pour éviter les interférences
        _cache.clear()

    def tearDown(self):
        self.ctx.pop()

    def test_health_check(self):
        """Vérifie la route de santé utilisée par Render"""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"ok")

    def test_home_page(self):
        """Vérifie que la page principale charge le HTML"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<!DOCTYPE html>", response.data)

    @patch('requests.get')
    def test_autocomplete_mock(self, mock_get):
        """Test de l'autocomplétion (utilise requests.get dans app.py)"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"name": "Paris", "country": "FR", "state": "Ile-de-France", "lat": 48.85, "lon": 2.35}
        ]
        mock_get.return_value = mock_resp

        response = self.client.get("/autocomplete?q=Paris")
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertEqual(len(data), 1)
        # Vérifie le formatage du label dicté par app.py
        self.assertEqual(data[0]['label'], "Paris, Ile-de-France, FR")

    def test_missing_city_parameter(self):
        """Erreur 400 si aucun paramètre n'est fourni"""
        response = self.client.get("/get_weather") 
        self.assertEqual(response.status_code, 400)
        self.assertIn("Veuillez fournir une ville valide", response.json["error"])

    # --- TESTS DES GESTIONS D'ERREURS (Unhappy Paths) ---

    @patch('requests.Session.get')
    def test_city_not_found_404(self, mock_session_get):
        """L'API renvoie 404 (Ville introuvable)"""
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_session_get.return_value = mock_resp

        response = self.client.get("/get_weather?city=AtlantisLostCity")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json["error"], "Ville introuvable.")

    @patch('requests.Session.get')
    def test_openweather_rate_limit_429(self, mock_session_get):
        """L'API renvoie 429 (Trop de requêtes) -> Transformé en 503"""
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_session_get.return_value = mock_resp

        response = self.client.get("/get_weather?city=Paris")
        self.assertEqual(response.status_code, 503)
        self.assertIn("temporairement surchargé", response.json["error"])

    @patch('requests.Session.get')
    def test_api_timeout_error(self, mock_session_get):
        """Crash réseau de type Timeout -> Transformé en 504"""
        mock_session_get.side_effect = requests.exceptions.Timeout("Trop long !")

        response = self.client.get("/get_weather?city=Paris")
        self.assertEqual(response.status_code, 504)
        self.assertIn("met trop de temps à répondre", response.json["error"])

    @patch('requests.Session.get')
    def test_api_connection_error(self, mock_session_get):
        """Crash réseau de type ConnectionError -> Transformé en 502"""
        mock_session_get.side_effect = requests.exceptions.ConnectionError("Coupure internet")

        response = self.client.get("/get_weather?city=Paris")
        self.assertEqual(response.status_code, 502)
        self.assertIn("Erreur de connexion", response.json["error"])

    # --- TESTS DU CAS NOMINAL ET DU CACHE ---

    @patch('requests.Session.get')
    def test_full_weather_api_logic(self, mock_session_get):
        """Test API standard : On vérifie le mapping des données de retour"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "weather": [{"description": "ciel clair", "icon": "01d"}],
            "main": {"temp": 25.0, "humidity": 40, "pressure": 1013, "feels_like": 24.0},
            "sys": {"country": "FR", "sunrise": 1600000000, "sunset": 1600050000},
            "wind": {"speed": 5.0},
            "coord": {"lat": 43.3, "lon": 5.4},
            "name": "Marseille",
            "visibility": 10000
        }
        mock_session_get.return_value = mock_resp

        response = self.client.get("/get_weather?city=Marseille")
        self.assertEqual(response.status_code, 200)
        
        data = response.json
        self.assertEqual(data['city'], "Marseille")
        self.assertEqual(data['temperature'], 25.0)
        self.assertEqual(data['description'], "ciel clair")

    @patch('requests.Session.get')
    def test_caching_mechanism(self, mock_session_get):
        """Test du cache LRU mémoire : la 2ème requête ne doit pas appeler l'API"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "name": "Lyon",
            "main": {"temp": 10},
        }
        mock_session_get.return_value = mock_resp

        # Appel 1 : L'API est appelée, le cache est vide
        response1 = self.client.get("/get_weather?city=Lyon")
        self.assertEqual(response1.status_code, 200)
        self.assertNotIn("_cached", response1.json)
        
        # Appel 2 : Les données viennent du cache
        response2 = self.client.get("/get_weather?city=Lyon")
        self.assertEqual(response2.status_code, 200)
        
        # Le code app.py injecte "_cached": True quand ça vient du cache !
        self.assertTrue(response2.json.get("_cached"))
        
        # requests.Session.get ne doit avoir été appelé qu'UNE SEULE FOIS
        self.assertEqual(mock_session_get.call_count, 1)

    # --- TEST DES ROUTES ANNEXES ---

    def test_download_readme(self):
        """Vérifie la route de téléchargement du README"""
        # Pour que ça marche dans le test, on s'assure que le fichier existe
        # Si le test est lancé à la racine du projet, ça passera.
        if os.path.exists("README.md"):
            response = self.client.get("/download/readme")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, "text/markdown")
            response.close() # <-- Ajoute cette ligne pour fermer le fichier et enlever le warning !

    def test_security_headers(self):
        """Vérifie que les headers de sécurité sont bien appliqués par la route"""
        response = self.client.get("/")
        self.assertIn('X-Content-Type-Options', response.headers)
        self.assertEqual(response.headers['X-Frame-Options'], 'DENY')

if __name__ == "__main__":
    unittest.main()