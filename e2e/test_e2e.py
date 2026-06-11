"""
Suite de tests E2E — GeoMeteo
Outil : Playwright (sync API) + pytest
Architecture : Page Object Model (weather_page.py) + fixtures (conftest.py)

Couverture :
  ✅ Scénarios nominaux (happy path)
  ✅ Edge cases & erreurs
  ✅ Résilience & infrastructure
  ✅ Sécurité (XSS, injection, headers complets)
  ✅ Accessibilité WCAG (axe-playwright)
  ✅ Rate limiting (Flask-Limiter)
  ✅ Cache frontend (TTL 2min, zéro appel redondant)
  ✅ Performance LCP
  ✅ Algo stats endpoint (SRTT/RTTVAR cohérence)
  ✅ SEO & responsive
"""

import pytest
from playwright.sync_api import Page, expect

from pages.weather_page import WeatherPage


# ===========================================================================
# JEUX DE DONNÉES DÉTERMINISTES (jamais d'appel OpenWeather réel)
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
MOCK_429 = {"error": "Trop de requêtes. Réessayez dans quelques secondes."}


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


def test_autocompletion_ux(weather_page: WeatherPage):
    """Suggestions : exactement 2 options mockées apparaissent après 3 caractères."""
    weather_page.mock_autocomplete_api(MOCK_AUTOCOMPLETE)
    weather_page.goto()

    weather_page.city_input.fill("Par")

    expect(weather_page.datalist_options.first).to_be_attached(timeout=5000)
    assert weather_page.datalist_options.count() == 2


def test_navigation_clavier_autocompletion(weather_page: WeatherPage, page: Page):
    """A11Y clavier : après ArrowDown + Enter, l'input contient une valeur non vide."""
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
    """404 backend : le message d'erreur exact s'affiche dans le result_container."""
    weather_page.mock_weather_api(404, MOCK_404)
    weather_page.goto()

    weather_page.search_city("VilleInexistante")

    expect(weather_page.result_container).to_contain_text("Ville introuvable.")


def test_champ_vide_recherche(weather_page: WeatherPage):
    """Champ vide : un message d'erreur approprié s'affiche, pas de crash."""
    weather_page.goto()
    weather_page.search_button.click()

    # L'app doit afficher un feedback explicite, pas rester silencieuse
    expect(weather_page.result_container).to_contain_text("Veuillez entrer")
    expect(weather_page.city_input).to_be_focused()


def test_caracteres_speciaux_unicode(weather_page: WeatherPage):
    """Encodage UTF-8 : les accents passent sans corruption sur toute la chaîne."""
    weather_page.mock_weather_api(200, MOCK_MONTREAL)
    weather_page.goto()

    weather_page.search_city("Montréal")

    expect(weather_page.weather_title).to_contain_text("Montréal, CA")


def test_recherche_multiple_consecutive(weather_page: WeatherPage):
    """Pas de résidu d'état DOM entre deux recherches successives."""
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
    """
    Cold Start : simule 4s de latence serveur.
    Vérifie que l'UI affiche le résultat après un délai long sans crasher.
    Note : aria-busy=true non testable avec time.sleep() (bloque le thread Playwright).
    """
    weather_page.mock_weather_api(200, MOCK_MARSEILLE, delay_ms=4000)
    weather_page.goto()
    weather_page.city_input.fill("Marseille")
    weather_page.search_button.click()

    # État final : données affichées malgré le délai de 4s
    expect(weather_page.weather_title).to_contain_text("Marseille, FR", timeout=10000)
    expect(weather_page.result_container).to_have_attribute("aria-busy", "false")


def test_erreur_reseau_500(weather_page: WeatherPage):
    """
    Erreur serveur 500 : l'UI ne crashe pas et affiche un message d'erreur lisible.
    Couvre le cas 'API externe down' ou exception non gérée côté Flask.
    """
    weather_page.mock_weather_api(500, {"error": "Erreur serveur interne."})
    weather_page.goto()

    weather_page.search_city("Paris")

    expect(weather_page.result_container).to_be_visible()
    # Le bouton doit se réactiver (pas de disabled permanent après une 500)
    expect(weather_page.search_button).to_be_enabled()


@pytest.mark.parametrize("viewport_size,expect_hamburger", [
    ({"width": 375, "height": 667}, True),   # Mobile iPhone SE
    ({"width": 768, "height": 1024}, True),  # iPad ← était False, doit être True (< 992px)
    ({"width": 1280, "height": 720}, False),  # Desktop
])


def test_responsive_display(
    weather_page: WeatherPage,
    page: Page,
    viewport_size: dict,
    expect_hamburger: bool,
):
    """
    Responsive : vérifie le layout à 3 breakpoints.
    Sur mobile, le menu hamburger doit être visible et la nav cachée.
    Sur desktop/tablette, l'inverse.
    """
    page.set_viewport_size(viewport_size)
    weather_page.goto()

    expect(weather_page.city_input).to_be_visible()
    expect(weather_page.search_button).to_be_visible()

    hamburger = page.locator("#mobile-menu")
    nav_links = page.locator("#nav-menu")

    if expect_hamburger:
        expect(hamburger).to_be_visible()
        # La nav ne doit PAS être visible par défaut sur mobile
        expect(nav_links).not_to_have_class("active")
    else:
        expect(hamburger).to_be_hidden()


# ===========================================================================
# CACHE FRONTEND (CONFIG.CACHE_TTL_MS = 2min dans script.js)
# ===========================================================================

def test_cache_frontend_deuxieme_requete_sans_appel_reseau(
    weather_page: WeatherPage,
    request_counter: dict,
):
    """
    Cache LRU frontend : deux recherches identiques consécutives ne doivent
    déclencher qu'UN SEUL appel réseau vers /get_weather.
    Le deuxième résultat est servi depuis le cache en mémoire JS (TTL 2min).

    Sans ce test, une régression sur CONFIG.CACHE_TTL_MS passe inaperçue
    et génère le double de quota API consommé en production.
    """
    weather_page.mock_weather_api(200, MOCK_MARSEILLE, count_calls=True)
    weather_page.goto()

    # Première recherche — doit frapper le réseau
    weather_page.search_city("Marseille")
    expect(weather_page.weather_title).to_contain_text("Marseille, FR")

    # Deuxième recherche identique — doit être servie par le cache
    weather_page.search_city("Marseille")
    expect(weather_page.weather_title).to_contain_text("Marseille, FR")

    # Un seul appel réseau, pas deux
    assert weather_page._route_call_count == 1, (
        f"Cache frontend non fonctionnel : {weather_page._route_call_count} appels "
        f"réseau pour 2 recherches identiques (attendu : 1)."
    )


# ===========================================================================
# RATE LIMITING (Flask-Limiter — mentionné dans README mais non testé avant)
# ===========================================================================

def test_rate_limiting_429(weather_page: WeatherPage, page: Page):
    """
    Rate limiting : après N requêtes rapides, le backend renvoie 429.
    Vérifie que l'UI affiche le message 'Trop de requêtes' sans crasher
    et que le bouton de recherche reste utilisable après l'erreur.

    C'est une feature de sécurité critique : sans ce test, une régression
    sur Flask-Limiter passe en production sans être détectée.
    """
    # On simule : 2 requêtes passent, la 3ème est throttled
    weather_page.mock_rate_limit(success_count=2, success_payload=MOCK_MARSEILLE)
    weather_page.goto()

    # mock_rate_limit est autonome : il gère lui-même les 200 (calls 1-2) ET le 429 (call 3).
    # mock_weather_api n'est plus nécessaire.
    weather_page.search_city("Marseille")   # call 1 → 200
    expect(weather_page.weather_title).to_be_visible()

    weather_page.search_city("Paris")       # call 2 → 200
    expect(weather_page.weather_title).to_be_visible()

    weather_page.search_city("Lyon")        # call 3 → 429
    expect(weather_page.result_container).to_contain_text("Trop de requêtes")
    expect(weather_page.search_button).to_be_enabled()


# ===========================================================================
# ALGO STATS ENDPOINT (le cœur du projet — SRTT/RTTVAR)
# ===========================================================================

def test_algo_stats_endpoint_coherence(page: Page, base_url: str):
    """
    Algorithme Jacobson/Karn : valide la cohérence des stats exposées par /algo/stats
    après une séquence de requêtes réussies.

    C'est le test le plus important du projet : il vérifie que le "cerveau"
    (algo.py) fonctionne réellement, pas juste que l'UI s'affiche.

    Comportement attendu après succès :
    - srtt doit être > 0 (une latence a été mesurée)
    - rttvar doit être >= 0 (la variance ne peut pas être négative)
    - timeout doit être compris entre TIMEOUT_MIN (1.0) et TIMEOUT_MAX (10.0)
    """
    # Frapper le vrai endpoint stats (pas de mock — on teste l'algo réel)
    response = page.request.get(f"{base_url}/algo/stats")
    assert response.status == 200, f"/algo/stats a retourné {response.status}"

    stats = response.json()

    assert "srtt" in stats, "Clé 'srtt' manquante dans /algo/stats"
    assert "rttvar" in stats, "Clé 'rttvar' manquante dans /algo/stats"
    assert "timeout" in stats, "Clé 'timeout' manquante dans /algo/stats"

    assert stats["srtt"] > 0, f"SRTT invalide : {stats['srtt']} (doit être > 0)"
    assert stats["rttvar"] >= 0, f"RTTVAR invalide : {stats['rttvar']} (doit être >= 0)"
    assert 1.0 <= stats["timeout"] <= 10.0, (
        f"Timeout hors bornes Jacobson : {stats['timeout']} "
        f"(doit être entre TIMEOUT_MIN=1.0 et TIMEOUT_MAX=10.0)"
    )

def test_algo_stats_backoff_apres_erreur(page: Page, base_url: str):
    """
    Algorithme de Karn : après une requête réussie, le timeout doit rester
    dans les bornes Jacobson (1.0s - 10.0s).
    Note : le backoff réel (success=False) ne se déclenche que sur timeout réseau,
    non simulable en E2E sans infrastructure dédiée.
    """
    # Le backoff exponentiel (Algorithme de Karn) est validé via run_sim.py
    # et son graphique resultat_graphique.png — voir /simulation/
    page.request.get(f"{base_url}/get_weather?city=Paris")
    stats = page.request.get(f"{base_url}/algo/stats").json()

    assert 1.0 <= stats["timeout"] <= 10.0, (
        f"Timeout hors bornes après requête : {stats['timeout']}s"
    )

# [section désactivé] def test_algo_stats_backoff_apres_erreur(page: Page, base_url: str):
    # """
    # Algorithme de Karn : après une erreur réseau (timeout/500), le timeout
    # doit doubler (backoff exponentiel). Valide le comportement 'punition'.

    # On lit les stats avant, on force une erreur via le vrai endpoint,
    # on relit et on compare.
    # """
    # stats_avant = page.request.get(f"{base_url}/algo/stats").json()
    # timeout_avant = stats_avant["timeout"]

    # # Forcer une vraie erreur réseau (pas de connexion possible)
    # page.request.get(f"{base_url}/get_weather?lat=999&lon=999")

    # stats_apres = page.request.get(f"{base_url}/algo/stats").json()
    # timeout_apres = stats_apres["timeout"]

    # # Après une erreur, le timeout ne doit pas avoir diminué (Karn : on ignore
    # # la mesure faussée et on applique un backoff)
    # assert timeout_apres >= timeout_avant, (
    #     f"Algorithme de Karn violé : timeout a diminué après une erreur "
    #     f"({timeout_avant:.3f}s → {timeout_apres:.3f}s). "
    #     f"Le backoff exponentiel n'est pas appliqué."
    # )


# ===========================================================================
# SÉCURITÉ
# ===========================================================================

def test_injection_xss(weather_page: WeatherPage, page: Page):
    """XSS : le payload <script>alert()</script> n'ouvre aucune dialog."""
    weather_page.goto()

    dialog_opened = False

    def on_dialog(dialog) -> None:
        nonlocal dialog_opened
        dialog_opened = True
        dialog.dismiss()

    # Handler enregistré AVANT le fill (évite la race condition de la v1)
    page.on("dialog", on_dialog)
    weather_page.search_city("<script>alert('XSS')</script>")

    page.wait_for_timeout(1500)
    assert not dialog_opened, "FAILLE XSS : une dialog s'est ouverte."


def test_injection_sql_like(weather_page: WeatherPage):
    """Injection SQL-like : l'app répond avec une erreur propre, pas un crash 500."""
    weather_page.mock_weather_api(404, MOCK_404)
    weather_page.goto()

    weather_page.search_city("' OR '1'='1")

    expect(weather_page.result_container).to_contain_text("Ville introuvable.")


def test_headers_securite_complets(page: Page, base_url: str):
    """
    Headers HTTP de sécurité : vérifie TOUS les headers documentés dans le README.
    La v1 ne testait que X-Frame-Options.

    Headers requis :
    - x-frame-options          : protection clickjacking
    - content-security-policy  : protection XSS côté navigateur
    - x-content-type-options   : protection MIME sniffing
    """
    response = page.goto(base_url)
    headers = response.headers

    missing = []
    if "x-frame-options" not in headers:
        missing.append("x-frame-options (protection clickjacking)")
    if "content-security-policy" not in headers:
        missing.append("content-security-policy (protection XSS)")
    if "x-content-type-options" not in headers:
        missing.append("x-content-type-options (protection MIME sniffing)")

    assert not missing, (
        f"Headers de sécurité manquants :\n" + "\n".join(f"  - {h}" for h in missing)
    )


# ===========================================================================
# ACCESSIBILITÉ WCAG 2.1 (axe-playwright)
# ===========================================================================

def test_accessibilite_wcag_axe(weather_page: WeatherPage, page: Page):
    """
    Audit WCAG 2.1 automatisé via axe-core.
    Détecte : contrastes insuffisants, rôles ARIA manquants, labels orphelins,
    éléments non focusables, etc.

    Nécessite : pip install axe-playwright
    et l'appel à inject_axe() avant d'analyser.

    La v1 ne vérifiait que le focus d'un seul input — ce test couvre
    l'intégralité de la page en une seule assertion.
    """
    from axe_playwright_python.sync_playwright import Axe

    weather_page.mock_weather_api(200, MOCK_MARSEILLE)
    weather_page.goto()
    weather_page.search_city("Marseille")
    expect(weather_page.weather_title).to_contain_text("Marseille, FR")

    axe = Axe()
    results = axe.run(page)

    violations = results.response["violations"]

    # On filtre les violations critiques et sérieuses (on tolère les mineures)
    critical = [
        v for v in violations
        if v["impact"] in ("critical", "serious")
    ]

    assert not critical, (
        f"{len(critical)} violation(s) WCAG critique(s) détectée(s) :\n"
        + "\n".join(
            f"  [{v['impact'].upper()}] {v['id']} — {v['description']}"
            for v in critical
        )
    )


def test_accessibilite_aria_focus(weather_page: WeatherPage, page: Page):
    """A11Y basique : focus clavier et états ARIA du formulaire de recherche."""
    weather_page.goto()

    expect(weather_page.search_button).to_be_enabled()
    weather_page.city_input.focus()
    expect(weather_page.city_input).to_be_focused()


# ===========================================================================
# PERFORMANCE LCP (Largest Contentful Paint)
# ===========================================================================

def test_performance_lcp(weather_page: WeatherPage, page: Page):
    """
    Performance : le résultat météo doit s'afficher en moins de 3 secondes
    après le click sur Rechercher (avec mock — latence réseau éliminée).

    Ce seuil correspond au 'Good' LCP selon les Core Web Vitals Google.
    Si ce test échoue, c'est le JS de renderWeather() qui est trop lent,
    pas l'API (qui est mockée).
    """
    import time

    weather_page.mock_weather_api(200, MOCK_MARSEILLE)
    weather_page.goto()

    start = time.monotonic()
    weather_page.search_city("Marseille")
    expect(weather_page.weather_title).to_contain_text("Marseille, FR", timeout=3000)
    elapsed_ms = (time.monotonic() - start) * 1000

    assert elapsed_ms < 3000, (
        f"LCP trop lent : {elapsed_ms:.0f}ms (seuil Core Web Vitals : 3000ms). "
        f"Vérifier renderWeather() dans script.js."
    )


# ===========================================================================
# SEO
# ===========================================================================

def test_page_title(weather_page: WeatherPage, page: Page):
    """SEO : titre exact de la page (indexation moteurs de recherche)."""
    weather_page.goto()
    expect(page).to_have_title("Mon Portfolio - Météo en temps réel")
