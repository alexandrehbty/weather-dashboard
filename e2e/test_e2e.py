"""
Suite de tests E2E consolidée — GeoMeteo
Outil : Playwright (sync API) + pytest
Architecture : Page Object Model (e2e/pages/weather_page.py) + fixtures intégrées

Couverture (24 cas) :
- Scénarios nominaux, carte Leaflet & autocomplétion clavier
- Erreurs & edge cases (404, champ vide, Unicode, recherches successives)
- Résilience & infrastructure (Cold Start, erreur 500, responsive 3 breakpoints)
- Cache frontend (TTL 2 min, 1 seul appel réseau) & Rate limiting (429)
- Observabilité de l'algorithme Jacobson/Karn (/algo/stats)
- Sécurité (XSS, injection SQL-like, headers HTTP complets dont HSTS)
- Accessibilité WCAG 2.1 (axe-core + focus ARIA), performance LCP & SEO
"""

import os
import re
import sys
import time

import pytest
from playwright.sync_api import Page, expect

# Garantit la résolution des imports en local comme en CI (PYTHONPATH=.)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from e2e.pages.weather_page import WeatherPage


# ===========================================================================
# FIXTURES PYTEST (anciennement dans conftest.py)
# ===========================================================================

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict) -> dict:
    """Configure le viewport par défaut et les téléchargements pour la session."""
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 720},
        "accept_downloads": True,
    }


@pytest.fixture
def weather_page(page: Page) -> WeatherPage:
    """Instancie le POM et nettoie systématiquement tous les mocks réseau après le test."""
    wp = WeatherPage(page)
    try:
        yield wp
    finally:
        page.unroute_all()


@pytest.fixture
def request_counter(page: Page) -> dict:
    """Compte les appels HTTP sortants du navigateur vers /get_weather."""
    counter = {"count": 0}

    def on_request(request) -> None:
        if "/get_weather" in request.url:
            counter["count"] += 1

    page.on("request", on_request)
    return counter


# ===========================================================================
# JEUX DE DONNÉES DÉTERMINISTES
# ===========================================================================

MOCK_MARSEILLE = {
    "city": "Marseille, FR",
    "temperature": 18.5,
    "description": "ciel dégagé",
    "icon": "01d",
    "wind_speed": 4.2,
    "humidity": 60,
    "pressure": 1015,
    "visibility": 10000,
    "sunrise": 1700000000,
    "sunset": 1700050000,
    "lat": 43.2965,
    "lon": 5.3698,
}

MOCK_LONDRES = {**MOCK_MARSEILLE, "city": "Londres, UK", "lat": 51.5074, "lon": -0.1278}
MOCK_MONTREAL = {**MOCK_MARSEILLE, "city": "Montréal, CA", "lat": 45.5017, "lon": -73.5673}

MOCK_AUTOCOMPLETE = [
    {"label": "Paris, Île-de-France, FR", "lat": 48.8566, "lon": 2.3522},
    {"label": "Parma, Emilia-Romagna, IT", "lat": 44.8015, "lon": 10.3279},
]

MOCK_404 = {"error": "Ville introuvable."}


# ===========================================================================
# SCÉNARIOS NOMINAUX ET UX
# ===========================================================================

def test_recherche_ville_succes(weather_page: WeatherPage):
    """Workflow nominal complet : les 7 cartes affichent les valeurs exactes du mock."""
    weather_page.mock_weather_api(200, MOCK_MARSEILLE)
    weather_page.goto()
    weather_page.search_city("Marseille")

    expect(weather_page.weather_title).to_contain_text("Marseille, FR")
    expect(weather_page.get_weather_card("Température")).to_contain_text("18.5°C")
    expect(weather_page.get_weather_card("Vent")).to_contain_text("4.2 m/s")
    expect(weather_page.get_weather_card("Humidité")).to_contain_text("60%")
    expect(weather_page.get_weather_card("Pression")).to_contain_text("1015 hPa")
    expect(weather_page.get_weather_card("Visibilité")).to_contain_text("10 km")
    expect(weather_page.get_weather_card("Lever")).to_be_visible()
    expect(weather_page.get_weather_card("Coucher")).to_be_visible()
    expect(weather_page.leaflet_map).to_be_visible()


def test_carte_leaflet_chargee(weather_page: WeatherPage):
    """Vérifie que la carte Leaflet.js s'initialise correctement dès le chargement."""
    weather_page.goto()
    expect(weather_page.leaflet_map).to_be_visible(timeout=5000)


def test_autocompletion_ux(weather_page: WeatherPage):
    """Suggestions : exactement 2 options mockées apparaissent après 3 caractères."""
    weather_page.mock_autocomplete_api(MOCK_AUTOCOMPLETE)
    weather_page.goto()

    weather_page.city_input.fill("Par")

    expect(weather_page.datalist_options.first).to_be_attached(timeout=5000)
    assert weather_page.datalist_options.count() == 2


def test_navigation_clavier_autocompletion(weather_page: WeatherPage, page: Page):
    """Accessibilité clavier : ArrowDown + Enter conserve une sélection non vide."""
    weather_page.mock_autocomplete_api(MOCK_AUTOCOMPLETE)
    weather_page.goto()

    weather_page.city_input.fill("Par")
    expect(weather_page.datalist_options.first).to_be_attached()

    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")

    expect(weather_page.city_input).not_to_be_empty()


# ===========================================================================
# SCÉNARIOS D'ERREURS ET EDGE CASES
# ===========================================================================

def test_erreur_ville_introuvable(weather_page: WeatherPage):
    """404 backend : le message d'erreur exact s'affiche dans le conteneur résultat."""
    weather_page.mock_weather_api(404, MOCK_404)
    weather_page.goto()

    weather_page.search_city("VilleInexistante")

    expect(weather_page.result_container).to_contain_text("Ville introuvable.")


def test_champ_vide_recherche(weather_page: WeatherPage):
    """Champ vide : feedback explicite et focus maintenu sur le champ."""
    weather_page.goto()
    weather_page.search_button.click()

    expect(weather_page.result_container).to_contain_text("Veuillez entrer")
    expect(weather_page.city_input).to_be_focused()


def test_caracteres_speciaux_unicode(weather_page: WeatherPage):
    """Encodage UTF-8 : les accents passent sans corruption sur toute la chaîne."""
    weather_page.mock_weather_api(200, MOCK_MONTREAL)
    weather_page.goto()

    weather_page.search_city("Montréal")

    expect(weather_page.weather_title).to_contain_text("Montréal, CA")


def test_recherche_multiple_consecutive(weather_page: WeatherPage):
    """Aucun résidu d'état DOM entre deux recherches successives."""
    weather_page.mock_weather_api(200, MOCK_MARSEILLE)
    weather_page.goto()
    weather_page.search_city("Marseille")
    expect(weather_page.weather_title).to_contain_text("Marseille, FR")

    weather_page.mock_weather_api(200, MOCK_LONDRES)
    weather_page.search_city("Londres")

    expect(weather_page.weather_title).to_contain_text("Londres, UK")
    expect(weather_page.weather_title).not_to_contain_text("Marseille")


# ===========================================================================
# RÉSILIENCE & INFRASTRUCTURE
# ===========================================================================

def test_cold_start_resilience(weather_page: WeatherPage):
    """Simule 4s de latence serveur (Cold Start) et vérifie le rendu final sans blocage."""
    weather_page.mock_weather_api(200, MOCK_MARSEILLE, delay_ms=4000)
    weather_page.goto()
    weather_page.city_input.fill("Marseille")
    weather_page.search_button.click()

    expect(weather_page.weather_title).to_contain_text("Marseille, FR", timeout=10000)
    expect(weather_page.result_container).to_have_attribute("aria-busy", "false")


def test_erreur_reseau_500(weather_page: WeatherPage):
    """Erreur serveur 500 : l'UI affiche un message lisible et réactive le bouton."""
    weather_page.mock_weather_api(500, {"error": "Erreur serveur interne."})
    weather_page.goto()

    weather_page.search_city("Paris")

    expect(weather_page.result_container).to_be_visible()
    expect(weather_page.search_button).to_be_enabled()


@pytest.mark.parametrize(
    "viewport_size,expect_hamburger",
    [
        ({"width": 375, "height": 667}, True),   # Mobile (iPhone SE)
        ({"width": 768, "height": 1024}, True),  # Tablette (< 992px)
        ({"width": 1280, "height": 720}, False), # Desktop
    ],
)
def test_responsive_display(
    weather_page: WeatherPage,
    page: Page,
    viewport_size: dict,
    expect_hamburger: bool,
):
    """Vérifie l'adaptation du layout et du menu mobile sur 3 breakpoints."""
    page.set_viewport_size(viewport_size)
    weather_page.goto()

    expect(weather_page.city_input).to_be_visible()
    expect(weather_page.search_button).to_be_visible()

    hamburger = page.locator("#mobile-menu")
    nav_links = page.locator("#nav-menu")

    if expect_hamburger:
        expect(hamburger).to_be_visible()
        expect(nav_links).not_to_have_class(re.compile(r"\bactive\b"))
    else:
        expect(hamburger).to_be_hidden()


# ===========================================================================
# CACHE FRONTEND & RATE LIMITING
# ===========================================================================

def test_cache_frontend_deuxieme_requete_sans_appel_reseau(
    weather_page: WeatherPage,
    request_counter: dict,
):
    """Deux recherches identiques consécutives ne doivent émettre qu'un seul appel réseau."""
    weather_page.mock_weather_api(200, MOCK_MARSEILLE)
    weather_page.goto()

    weather_page.search_city("Marseille")
    expect(weather_page.weather_title).to_contain_text("Marseille, FR")

    weather_page.search_city("Marseille")
    expect(weather_page.weather_title).to_contain_text("Marseille, FR")

    assert request_counter["count"] == 1, (
        f"Cache frontend défaillant : {request_counter['count']} appels "
        "réseau pour 2 recherches identiques (attendu : 1)."
    )


def test_rate_limiting_429(weather_page: WeatherPage):
    """Après N requêtes réussies, une réponse 429 affiche un message clair sans bloquer l'UI."""
    weather_page.mock_rate_limit(success_count=2, success_payload=MOCK_MARSEILLE)
    weather_page.goto()

    weather_page.search_city("Marseille")
    expect(weather_page.weather_title).to_be_visible()

    weather_page.search_city("Paris")
    expect(weather_page.weather_title).to_be_visible()

    weather_page.search_city("Lyon")
    expect(weather_page.result_container).to_contain_text("Trop de requêtes")
    expect(weather_page.search_button).to_be_enabled()


# ===========================================================================
# OBSERVABILITÉ ALGORITHME JACOBSON/KARN (/algo/stats)
# ===========================================================================

def test_algo_stats_endpoint_coherence(page: Page, base_url: str):
    """Vérifie le contrat et les bornes RFC 6298 de l'endpoint réel /algo/stats."""
    response = page.request.get(f"{base_url}/algo/stats")
    assert response.status == 200, f"/algo/stats a retourné {response.status}"

    stats = response.json()
    for key in ("srtt", "rttvar", "timeout", "idle_sec"):
        assert key in stats, f"Clé '{key}' manquante dans /algo/stats"

    assert stats["srtt"] > 0, f"SRTT invalide : {stats['srtt']}"
    assert stats["rttvar"] >= 0, f"RTTVAR invalide : {stats['rttvar']}"
    assert stats["idle_sec"] >= 0, f"idle_sec invalide : {stats['idle_sec']}"
    assert 1.0 <= stats["timeout"] <= 10.0, (
        f"Timeout hors bornes Jacobson : {stats['timeout']}s (attendu : 1.0s - 10.0s)"
    )


def test_algo_stats_apres_requete_backend(page: Page, base_url: str):
    """Vérifie que /algo/stats reste cohérent après une requête réelle sur /get_weather."""
    page.request.get(f"{base_url}/get_weather?city=Paris")
    response = page.request.get(f"{base_url}/algo/stats")
    assert response.status == 200

    stats = response.json()
    assert 1.0 <= stats["timeout"] <= 10.0, (
        f"Timeout hors bornes après requête : {stats['timeout']}s"
    )


# ===========================================================================
# SÉCURITÉ
# ===========================================================================

def test_injection_xss(weather_page: WeatherPage, page: Page):
    """Un payload <script> dans le champ ne déclenche aucune exécution JS dans le DOM."""
    weather_page.mock_weather_api(404, MOCK_404)
    weather_page.goto()

    dialog_opened = False

    def on_dialog(dialog) -> None:
        nonlocal dialog_opened
        dialog_opened = True
        dialog.dismiss()

    page.on("dialog", on_dialog)
    weather_page.search_city("<script>alert('XSS')</script>")

    expect(weather_page.result_container).to_contain_text("Ville introuvable.")
    assert not dialog_opened, "FAILLE XSS : une boîte de dialogue s'est ouverte."
    assert page.locator("#weather-result script").count() == 0, (
        "FAILLE XSS : une balise <script> a été injectée dans #weather-result."
    )


def test_injection_sql_like(weather_page: WeatherPage):
    """Une chaîne SQL-like renvoie une erreur propre (404), jamais un crash."""
    weather_page.mock_weather_api(404, MOCK_404)
    weather_page.goto()

    weather_page.search_city("' OR '1'='1")

    expect(weather_page.result_container).to_contain_text("Ville introuvable.")


def test_headers_securite_complets(page: Page, base_url: str):
    """Vérifie tous les headers de sécurité et de corrélation documentés dans le README."""
    response = page.goto(base_url)
    assert response is not None
    headers = response.headers

    required = {
        "x-frame-options": "protection clickjacking",
        "content-security-policy": "protection XSS",
        "x-content-type-options": "protection MIME sniffing",
        "strict-transport-security": "HSTS",
        "x-request-id": "corrélation des logs",
    }
    missing = [
        f"{header} ({desc})"
        for header, desc in required.items()
        if header not in headers
    ]

    assert not missing, "Headers HTTP manquants :\n" + "\n".join(f"  - {m}" for m in missing)


# ===========================================================================
# ACCESSIBILITÉ WCAG 2.1 (axe-core & ARIA)
# ===========================================================================

def test_accessibilite_wcag_axe(weather_page: WeatherPage, page: Page):
    """Audit WCAG 2.1 automatisé : zéro violation critique ou sérieuse tolérée."""
    from axe_playwright_python.sync_playwright import Axe

    weather_page.mock_weather_api(200, MOCK_MARSEILLE)
    weather_page.goto()
    weather_page.search_city("Marseille")
    expect(weather_page.weather_title).to_contain_text("Marseille, FR")

    results = Axe().run(page)
    violations = results.response["violations"]
    critical = [v for v in violations if v["impact"] in ("critical", "serious")]

    assert not critical, (
        f"{len(critical)} violation(s) WCAG critique(s)/sérieuse(s) détectée(s) :\n"
        + "\n".join(
            f"  [{v['impact'].upper()}] {v['id']} — {v['description']}"
            for v in critical
        )
    )


def test_accessibilite_aria_focus(weather_page: WeatherPage):
    """Vérifie le focus clavier et l'activation du bouton de recherche."""
    weather_page.goto()

    expect(weather_page.search_button).to_be_enabled()
    weather_page.city_input.focus()
    expect(weather_page.city_input).to_be_focused()


# ===========================================================================
# PERFORMANCE LCP & SEO
# ===========================================================================

def test_performance_lcp(weather_page: WeatherPage):
    """Le rendu frontend (hors réseau) doit rester sous le seuil Core Web Vitals de 3000ms."""
    weather_page.mock_weather_api(200, MOCK_MARSEILLE)
    weather_page.goto()

    start = time.monotonic()
    weather_page.search_city("Marseille")
    expect(weather_page.weather_title).to_contain_text("Marseille, FR", timeout=3000)
    elapsed_ms = (time.monotonic() - start) * 1000

    assert elapsed_ms < 3000, (
        f"Rendu trop lent : {elapsed_ms:.0f}ms (seuil : 3000ms). Vérifier renderWeather()."
    )


def test_page_title(weather_page: WeatherPage, page: Page):
    """SEO : vérifie le titre exact de la page."""
    weather_page.goto()
    expect(page).to_have_title("Mon Portfolio - Météo en temps réel")