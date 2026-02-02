import unittest
from unittest.mock import patch, MagicMock
import time
import sys
import os
import requests

# Ajoute le dossier parent au path pour importer app et algo
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from algo import PortfolioBrain

class TestPortfolioBrain(unittest.TestCase):
    """Test de l'intelligence artificielle (Jacobson/Karn)"""

    def setUp(self):
        self.brain = PortfolioBrain()

    def test_initial_values(self):
        """Vérifie que le cerveau démarre avec les valeurs par défaut"""
        self.assertEqual(self.brain.srtt, 3.0)
        self.assertEqual(self.brain.rttvar, 0.5)
        # Calcul initial : 3.0 + 4*0.5 = 5.0
        self.assertEqual(self.brain.get_timeout(), 5.0)

    def test_jacobson_update_success(self):
        """Si le réseau est RAPIDE et STABLE, le timeout doit baisser"""
        # On insiste 50 fois pour que la variance (l'inquiétude du cerveau) retombe à zéro
        for _ in range(50):
            self.brain.update(observed_latency=0.1, success=True)
        
        # Maintenant, le cerveau devrait être ultra-confiant (~0.1s + petite marge)
        self.assertLess(self.brain.get_timeout(), 5.0)

    def test_karn_penalty_failure(self):
        """Si échec (timeout), on doit punir (doubler le timeout)"""
        initial_timeout = self.brain.get_timeout()
        
        # On signale un échec
        self.brain.update(observed_latency=10.0, success=False)
        
        # Le timeout doit avoir doublé (borné à MAX=10.0)
        expected = min(10.0, initial_timeout * 2)
        self.assertEqual(self.brain.get_timeout(), expected)

class TestGeoMeteoApp(unittest.TestCase):
    """Test des routes Flask (API)"""

    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        self.client = app.test_client()

    def tearDown(self):
        self.ctx.pop()

    def test_health_check(self):
        """La route /health doit répondre 200 OK très vite"""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)

    def test_home_page(self):
        """La page d'accueil doit charger le template index.html"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        # On vérifie qu'on a bien du HTML
        self.assertIn(b"<!DOCTYPE html>", response.data)

    @patch('requests.get')
    def test_autocomplete_mock(self, mock_get):
        """Test de l'autocomplétion avec une fausse réponse API (Mock)"""
        # On simule une réponse de OpenWeather
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"name": "Paris", "country": "FR", "lat": 48.85, "lon": 2.35}
        ]
        mock_get.return_value = mock_resp

        response = self.client.get("/autocomplete?q=Paris")
        
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['label'], "Paris, FR")

    def test_missing_city_parameter(self):
        """Test : Que se passe-t-il si on cherche une météo sans donner de ville ?"""
        # Note: Assure-toi que cette route existe bien dans ton app.py
        # Si ta route météo est sur la page d'accueil, utilise "/" au lieu de "/api/weather"
        response = self.client.get("/api/weather") 
        self.assertNotEqual(response.status_code, 200)

    @patch('requests.get')
    def test_openweather_failure(self, mock_get):
        """Test : Que se passe-t-il si OpenWeather est en panne (Erreur 500) ?"""
        mock_resp = MagicMock()
        mock_resp.status_code = 500 
        mock_get.return_value = mock_resp

        response = self.client.get("/api/weather?city=Paris")
        self.assertNotEqual(response.status_code, 200)

    # --- NOUVEAUX TESTS POUR LA COUVERTURE (Unhappy Paths) ---

    @patch('requests.Session.get')
    def test_city_not_found_404(self, mock_get):
        """Test: Si l'utilisateur tape une ville qui n'existe pas"""
        # On simule OpenWeather qui répond "404 Not Found"
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.json.return_value = {"cod": "404", "message": "city not found"}
        mock_get.return_value = mock_resp

        # On appelle ta route avec une ville bidon
        response = self.client.get("/?city=AtlantisLostCity")
        
        # Ton app ne doit PAS planter (500). Elle doit afficher la page (200) avec un message d'erreur.
        self.assertEqual(response.status_code, 200)
        # On vérifie qu'on n'a pas crashé
        self.assertIn(b"<!DOCTYPE html>", response.data)

    @patch('requests.Session.get')
    def test_api_connection_error(self, mock_get):
        """Test: Si OpenWeather est totalement inaccessible (Coupure internet/DNS)"""
        # On simule un CRASH réseau violent
        mock_get.side_effect = requests.exceptions.ConnectionError("Pas d'internet")

        response = self.client.get("/?city=Paris")
        
        # Ton code a un 'except requests.exceptions.ConnectionError' ? Ce test va passer dedans.
        self.assertEqual(response.status_code, 200)
        # Idéalement, on cherche un message d'erreur dans le HTML
        # self.assertIn(b"Erreur de connexion", response.data) 

    @patch('requests.Session.get')
    def test_api_timeout_error(self, mock_get):
        """Test: Si OpenWeather est trop lent (Test de ton algo Jacobson !)"""
        # On simule un Timeout
        mock_get.side_effect = requests.exceptions.Timeout("Trop long !")

        response = self.client.get("/?city=Paris")
        
        # Cela doit déclencher ton bloc 'except requests.exceptions.Timeout'
        self.assertEqual(response.status_code, 200)

    def test_input_sanitization_empty(self):
        """Test: Si l'utilisateur envoie un champ vide"""
        response = self.client.get("/?city=")
        # Ton code doit probablement ignorer ou renvoyer la page d'accueil sans erreur
        self.assertEqual(response.status_code, 200)

    def test_input_sanitization_injection(self):
        """Test: Sécurité - Si l'utilisateur tente une injection bizarre"""
        # Ton validateur _parse_city doit bloquer ça ou le nettoyer
        response = self.client.get("/?city=<script>alert('hack')</script>")
        self.assertEqual(response.status_code, 200)
        # On vérifie que le script n'est pas exécuté (bonus)
        self.assertNotIn(b"<script>alert", response.data)

    # ==================================================================
    # ZONE DE TESTS "SENIOR" : TEST DU MOTEUR API (CORRIGÉ)
    # ==================================================================

    @patch('requests.Session.get')
    def test_full_weather_api_logic(self, mock_get):
        """
        🎯 TEST API : On vérifie que le JSON renvoyé par Python est bon.
        Route réelle : /get_weather
        """
        # 1. On simule la réponse d'OpenWeather (Données complètes pour éviter les erreurs)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "weather": [{"description": "ciel clair", "icon": "01d"}],
            "main": {"temp": 25.0, "humidity": 40, "pressure": 1013, "feels_like": 24.0},
            "sys": {"country": "FR", "sunrise": 1600000000, "sunset": 1600050000},
            "wind": {"speed": 5.0},
            "coord": {"lat": 43.3, "lon": 5.4},
            "name": "Marseille",
            "cod": 200,
            "visibility": 10000
        }
        mock_get.return_value = mock_resp

        # 2. On appelle TA VRAIE ROUTE (/get_weather)
        response = self.client.get("/get_weather?city=Marseille")

        # 3. Vérifications
        self.assertEqual(response.status_code, 200)
        
        # 4. On vérifie les données renvoyées par ton app.py
        data = response.json
        self.assertEqual(data['city'], "Marseille")
        # Ton app convertit "temp" en "temperature", on vérifie ça :
        self.assertIn('temperature', data) 
        self.assertEqual(data['temperature'], 25.0)

    @patch('requests.Session.get')
    def test_caching_mechanism(self, mock_get):
        """
        ⚡ TEST CACHE : On appelle l'API deux fois, elle ne doit bosser qu'une fois.
        """
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "weather": [{"description": "test", "icon": "01d"}],
            "main": {"temp": 10, "humidity": 10, "pressure": 1000, "feels_like": 9},
            "sys": {"country": "FR", "sunrise": 100, "sunset": 200},
            "wind": {"speed": 1},
            "coord": {"lat": 0, "lon": 0},
            "name": "Lyon",
            "cod": 200
        }
        mock_get.return_value = mock_resp

        # Appel 1 (Remplissage du cache) -> /get_weather
        self.client.get("/get_weather?city=Lyon")
        
        # Appel 2 (Lecture du cache) -> /get_weather
        self.client.get("/get_weather?city=Lyon")

        # VERDICT : requests.get ne doit avoir été appelé qu'UNE SEULE FOIS
        self.assertEqual(mock_get.call_count, 1)

    def test_security_headers(self):
        """🔒 TEST SÉCURITÉ : Headers sur la page d'accueil"""
        response = self.client.get("/")
        self.assertIn('X-Content-Type-Options', response.headers)

if __name__ == "__main__":
    unittest.main()