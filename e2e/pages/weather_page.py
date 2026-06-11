import time
from playwright.sync_api import Page, Locator, Route, expect


class WeatherPage:
    """
    Page Object Model — GeoMeteo.
    Centralise TOUS les sélecteurs et toutes les interactions avec l'UI.
    Principe : les tests ne connaissent pas le DOM, ils parlent au POM.
    """

    def __init__(self, page: Page):
        self.page = page

        # --- Sélecteurs stables (IDs sémantiques > classes CSS) ---
        self.city_input      = page.locator("#city-input")
        self.search_button   = page.locator("#search-btn")
        self.result_container = page.locator("#weather-result")
        self.weather_title   = page.locator(".weather-info h3")
        self.leaflet_map     = page.locator(".leaflet-container")
        self.datalist_options = page.locator("#city-suggestions option")

        # Compteur d'appels réseau — utilisé par test_cache_frontend
        self._route_call_count: int = 0

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def goto(self) -> None:
        """Charge la page depuis la base_url injectée par pytest (--base-url)."""
        self.page.goto("/")

    # ------------------------------------------------------------------
    # Actions utilisateur
    # ------------------------------------------------------------------

    def search_city(self, city_name: str) -> None:
        self.city_input.fill(city_name)
        self.search_button.click()

    def get_weather_card(self, label: str) -> Locator:
        return self.page.locator(".weather-card").filter(has_text=label)

    # ------------------------------------------------------------------
    # Mocking réseau (page.route — déterminisme total, zéro appel externe)
    # ------------------------------------------------------------------

    def mock_weather_api(
        self,
        status_code: int,
        json_payload: dict,
        delay_ms: int = 0,
        count_calls: bool = False,
    ) -> None:
        """
        Intercepte GET /get_weather*.
        - delay_ms  : simule une latence serveur (Cold Start, congestion).
                      Utilise time.sleep() — jamais page.wait_for_timeout()
                      dans un handler route (deadlock Playwright garanti).
        - count_calls : active le compteur self._route_call_count (test cache).
        """
        self._route_call_count = 0

        def handle(route: Route) -> None:
            if count_calls:
                self._route_call_count += 1
            if delay_ms > 0:
                time.sleep(delay_ms / 1000)   # ← sleep OS, pas Playwright
            route.fulfill(
                status=status_code,
                content_type="application/json",
                json=json_payload,
            )

        self.page.route("**/get_weather*", handle)

    def mock_autocomplete_api(self, json_payload: list) -> None:
        self.page.route(
            "**/autocomplete*",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                json=json_payload,
            ),
        )

    def mock_rate_limit(self, success_count: int, success_payload: dict) -> None:
        """
        Handler unique stateful : les N premiers calls → 200, ensuite → 429.
        """
        self.page.unroute("**/get_weather*")   # nettoie tout handler précédent
        counter = {"n": 0}
        
        def handle(route):
            counter["n"] += 1
            if counter["n"] <= success_count:
                route.fulfill(status=200, content_type="application/json", json=success_payload)
            else:
                route.fulfill(status=429, content_type="application/json", json={"error": "Trop de requêtes. Réessayez dans quelques secondes."})  

        self.page.route("**/get_weather*", handle)
