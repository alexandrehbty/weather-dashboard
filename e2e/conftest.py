import pytest
from playwright.sync_api import Page
from e2e.pages.weather_page import WeatherPage


# ---------------------------------------------------------------------------
# Configuration globale du contexte browser
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict) -> dict:
    """
    Configure viewport et options du contexte pour toute la session.
    scope="session" : créé une seule fois, partagé entre tous les tests.
    """
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 720},
        "accept_downloads": True,
    }


# ---------------------------------------------------------------------------
# Fixture principale : Page Object Model
# ---------------------------------------------------------------------------

@pytest.fixture
def weather_page(page: Page, base_url: str) -> WeatherPage:
    """
    Instancie le POM et garantit un nettoyage complet après chaque test.

    Pourquoi yield + unroute_all() ?
    Sans teardown, un mock installé par un test qui ÉCHOUE reste actif.
    Le test suivant hérite de ce mock et produit un faux positif ou faux négatif
    silencieux — le bug le plus difficile à diagnostiquer en CI.

    unroute_all() supprime TOUS les handlers page.route() actifs.
    """
    wp = WeatherPage(page)
    yield wp
    page.unroute_all()   # ← teardown garanti, même si le test lève une exception


# ---------------------------------------------------------------------------
# Fixture utilitaire : compteur de requêtes réseau
# ---------------------------------------------------------------------------

@pytest.fixture
def request_counter(page: Page) -> dict:
    """
    Compteur générique d'appels réseau vers /get_weather.
    Usage : assert request_counter["count"] == 1

    Indépendant du POM pour pouvoir être combiné avec weather_page
    dans des tests qui ont besoin des deux.
    """
    counter = {"count": 0}

    def on_request(request) -> None:
        if "/get_weather" in request.url:
            counter["count"] += 1

    page.on("request", on_request)
    return counter
